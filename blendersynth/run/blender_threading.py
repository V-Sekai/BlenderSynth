import sys
from tqdm import tqdm
from time import perf_counter, sleep
import numpy as np
from subprocess import Popen

from .blender_interface import LOG_PREPEND
from datetime import datetime, timedelta
import os


def list_split(list, chunks):
	"""Split a list into chunks"""
	return [[*x] for x in np.array_split(list, chunks)]

class BlenderThread():
	def __init__(self, command, jobs, log_loc, name='', timeout=100, to_stdout=False,
				 MAX_PER_JOB=100):
		"""Timeout: longest time in (s) without render after which process is finished.
		MAX_PER_JOB: Split command into jobs of size MAX_PER_JOB, and run each job in a separate process."""

		self.command = command
		self.jobs = list_split(jobs, np.ceil(len(jobs)/MAX_PER_JOB)) # split jobs into chunks of MAX_PER_JOB
		self.njobs = len(self.jobs)

		self.size = len(jobs)
		self.timeout = timeout

		self.prev_n = 0  # store how many rendered to check for updates for timeout purposes
		self.timer = perf_counter()

		self.to_stdout = to_stdout
		if not self.to_stdout and log_loc is not None:
			self.log_loc = log_loc
			self.logfile = open(self.log_loc, "a")
		else:
			self.log_loc, self.logfile = None, None


		self.process = None
		self.job = -1
		self.finished = False

		self.name = name
		self.status = f'STARTED THREAD {self.name}'

	def check_in(self):
		"""Checks if current job still running, if not move to next job.
		If all jobs complete, set self.finished = True"""
		if self.is_running:
			return

		self.job += 1

		if self.job >= self.njobs:
			self.finished = True
			self.status = f'✓ THREAD {self.name} COMPLETED.'
			return

		self.status = f"THREAD {self.name} RUNNING JOB {self.job+1}/{self.njobs}..."
		self.start_job(self.job)

	def start_job(self, job=0):
		job_list = self.jobs[job]
		command = self.command.set_job(job_list)

		stdout = sys.stdout if self.to_stdout else self.logfile
		stderr = sys.stderr if self.to_stdout else self.logfile
		self.process = Popen(command, universal_newlines=True, stdout=stdout, stderr=stderr)

	def terminate(self):
		self.process.kill()

	@property
	def is_running(self):
		if self.process:
			return self.process.poll() is None
		return False

	@property
	def complete(self):
		if not self.is_running:
			self.logfile.flush()
			return True

	def __len__(self):
		return self.size

	@property
	def num_rendered(self):
		"""Read through Log file to find how many renders have been completed"""
		if self.process is None:
			return 0 # process not started yet

		if self.to_stdout:
			reader = sys.stdout
		else:
			reader = open(self.log_loc, "r").readlines()

		x = 0
		for line in reader:
			if line.startswith(LOG_PREPEND):
				x += 1

		return x

	def remaining_idxs(self):
		raise NotImplementedError()

	@property
	def success(self):
		return self.num_rendered == self.size

	def check_status(self):
		"""True if still running succesfully, False if exceeded timeout"""
		n = self.num_rendered
		if n > self.prev_n:
			self.prev_n = n
			self.timer = perf_counter()

		elif (perf_counter() - self.timer) >= self.timeout:
			return False

		return True

class BlenderThreadManager:
	def __init__(self, command, jsons, output_directory, print_to_stdout=False,
				 MAX_PER_JOB=100):
		"""
		:param commands: Base Blender command to run
		:param jsons: A list of num_threads size, each element is a list of jsons to render from
		:param log_locs:
		:param MAX_PER_JOB: To prevent memory issues, split up jobs into chunks of MAX_PER_JOB
		"""
		self.num_threads = len(jsons)

		self.command = command

		# create logs
		session_name = datetime.now().strftime(r"%y%m%d-%H%M%S")
		log_dir = os.path.join(output_directory, 'logs', session_name)

		os.makedirs(log_dir, exist_ok=True)
		logs = [os.path.join(log_dir, f'log_{i:02d}.txt') for i in range(self.num_threads)]
		self.log_locs = logs

		# Set report name as report_xx, incrementing by 1 each report
		report_fname = f"report_{len([f for f in os.listdir(output_directory) if 'report' in f]):02d}.txt"
		self.report_loc = os.path.join(output_directory, report_fname)

		self.t0 = 0
		self.session_start = None

		self.threads = []
		for i in range(self.num_threads):
			thread = BlenderThread(command,
								   jobs = jsons[i],
								   log_loc=None if logs is None else logs[i],
								   name=str(i),
								   to_stdout=print_to_stdout,
								   MAX_PER_JOB=MAX_PER_JOB)
			self.threads.append(thread)

	def __len__(self):
		return sum(map(len, self.threads))

	def start(self, progress_bars=True,
			  tick=0.5, report_every=15,
			  ):
		"""Start all threads and job progress
		:param progress_bars: If True, show progress bars for each thread and overall progress
		:param tick: How often to update progress bars
		:param report_every: How often to print status updates to log
		"""
		self.t0 = perf_counter()  # log start time
		self.session_start = datetime.now()
		for thread in self.threads:
			thread.check_in()

		last_report_time = perf_counter()

		if progress_bars:
			pbars = []
			bar_format = '{l_bar}{bar:10}{r_bar}{bar:-10b}'
			for i, thread in enumerate(self.threads):
				p = tqdm(total=len(thread), initial=thread.num_rendered, bar_format=bar_format,
						 position=i + 1)
				pbars.append(p)

			with tqdm(total=len(self), bar_format=bar_format, position=0) as pbar:
				while any(t.is_running for t in self.threads):
					sleep(tick)

					# Update progress bar
					rendered_images = self.num_rendered

					desc = 'Session rendering...'
					desc += f' [Dataset: {rendered_images}/{len(self)}]'
					pbar.set_description(desc)

					pbar.n = self.num_rendered
					pbar.refresh()

					if (perf_counter() - last_report_time) >= report_every:
						self.update_report()
						last_report_time = perf_counter()

					# Update sub-progress bars, restart threads if needed
					for t, thread in enumerate(self.threads):

						if thread.finished:
							continue

						thread.check_in()

						if thread.success:
							pbars[t].n = thread.num_rendered

						else:
							thread_running = thread.check_status()

							if thread_running:
								pbars[t].n = thread.num_rendered

							else:  # Thread failed, restart thread
								print("CANNOT DEAL WITH FAILED THREADS YET")

						pbars[t].set_description(thread.status)

			self.update_report()

	@property
	def num_rendered(self):
		return sum(t.num_rendered for t in self.threads)

	def update_report(self):

		t1 = perf_counter()
		elapsed = t1 - self.t0

		report = []
		if self.num_rendered > 0:
			# calculate number of seconds remaining
			s_remaining = (len(self) - self.num_rendered) * (elapsed / self.num_rendered)
			eta = datetime.now() + timedelta(seconds=s_remaining)

			report += [
				f"Number of images rendered: {self.num_rendered}\n",
				f"Total session quota: {len(self)}\n",
				f"Time elapsed: {timedelta(seconds=round(elapsed))}\n",
				f"Time per render (s): {elapsed / self.num_rendered:.2f}\n\n",

				f"Session start: {self.session_start.strftime('%I:%M %p %d/%m/%y')}\n"
				f"Estimated End: {eta.strftime('%I:%M %p %d/%m/%y')}"
			]

		with open(self.report_loc, 'w') as outfile:
			outfile.writelines(report)