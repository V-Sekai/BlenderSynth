import bpy

ENGINES = ['BLENDER_EEVEE', 'BLENDER_WORKBENCH', 'CYCLES']
"""List of valid render engines"""


def render(animation:bool=False):
	"""Render the scene

	:param animation: If True, render the animation. Otherwise, render a single frame."""
	if animation:
		bpy.ops.render.render(animation=True)
	else:
		bpy.ops.render.render(write_still=True)


def set_engine(engine: str):
	"""Set the render engine

	:param engine: The render engine to use. See :data:`~blendersynth.blender.render.ENGINES` for valid options."""
	assert engine in ENGINES, "Invalid render engine"
	bpy.context.scene.render.engine = engine


def set_resolution(x: int, y: int):
	"""Set the render resolution

	:param x: The width of the image in pixels
	:param y: The height of the image in pixels"""
	bpy.context.scene.render.resolution_x = x
	bpy.context.scene.render.resolution_y = y


def set_cycles_samples(samples: int):
	"""Set the number of samples for the Cycles renderer"""
	assert bpy.context.scene.render.engine == 'CYCLES', "Cycles must be the active render engine"
	bpy.context.scene.cycles.samples = samples


def render_depth():
	"""Enable the depth pass of the renderer"""
	bpy.context.view_layer.use_pass_z = True  # enable depth pass


def set_transparent(scene=None):
	"""Set the background of the scene to transparent

	:param scene: The scene to set the background of. If None, use the active scene.
	"""
	if scene is None:
		scene = bpy.context.scene
	scene.render.film_transparent = True
