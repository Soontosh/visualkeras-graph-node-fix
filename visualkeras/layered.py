import aggdraw
from PIL import ImageFont
from math import ceil
from .utils import *
from .layer_utils import *

# TODO: Add example file for reversed view
# TODO: Add section in README for reversed view

def layered_view(model, to_file: str = None, min_z: int = 20, min_xy: int = 20, max_z: int = 400,
                 max_xy: int = 2000,
                 scale_z: float = 0.1, scale_xy: float = 4, type_ignore: list = None, index_ignore: list = None,
                 draw_reversed: bool = False,
                 color_map: dict = None, one_dim_orientation: str = 'z', index_2D: list = [],
                 background_fill: Any = 'white', draw_volume: bool = True, padding: int = 10,
                 spacing: int = 10, draw_funnel: bool = True, shade_step=10, legend: bool = False,
                 font: ImageFont = None, font_color: Any = 'black') -> Image:
    """
    Generates a architecture visualization for a given linear keras model (i.e. one input and output tensor for each
    layer) in layered style (great for CNN).

    :param model: A keras model that will be visualized.
    :param to_file: Path to the file to write the created image to. If the image does not exist yet it will be created, else overwritten. Image type is inferred from the file ending. Providing None will disable writing.
    :param min_z: Minimum z size in pixel a layer will have.
    :param min_xy: Minimum x and y size in pixel a layer will have.
    :param max_z: Maximum z size in pixel a layer will have.
    :param max_xy: Maximum x and y size in pixel a layer will have.
    :param scale_z: Scalar multiplier for the z size of each layer.
    :param scale_xy: Scalar multiplier for the x and y size of each layer.
    :param type_ignore: List of layer types in the keras model to ignore during drawing.
    :param index_ignore: List of layer indexes in the keras model to ignore during drawing.
    :param color_map: Dict defining fill and outline for each layer by class type. Will fallback to default values for not specified classes.
    :param one_dim_orientation: Axis on which one dimensional layers should be drawn. Can  be 'x', 'y' or 'z'.
    :param index_2D: When draw_volume is True, the indexes in this list will be drawn in 2D.
    :param background_fill: Color for the image background. Can be str or (R,G,B,A).
    :param draw_volume: Flag to switch between 3D volumetric view and 2D box view.
    :param draw_reversed: Draw 3D boxes reversed, going from front-right to back-left.
    :param padding: Distance in pixel before the first and after the last layer.
    :param spacing: Spacing in pixel between two layers
    :param draw_funnel: If set to True, a funnel will be drawn between consecutive layers
    :param shade_step: Deviation in lightness for drawing shades (only in volumetric view)
    :param legend: Add a legend of the layers to the image
    :param font: Font that will be used for the legend. Leaving this set to None, will use the default font.
    :param font_color: Color for the font if used. Can be str or (R,G,B,A).

    :return: Generated architecture image.
    """

    # Iterate over the model to compute bounds and generate boxes

    boxes = list()
    layer_y = list()
    color_wheel = ColorWheel()
    current_z = padding
    x_off = -1

    layer_types = list()

    img_height = 0
    max_right = 0

    if type_ignore is None:
        type_ignore = list()

    if index_ignore is None:
        index_ignore = list()

    if color_map is None:
        color_map = dict()

    for index, layer in enumerate(model.layers):

        # Ignore layers that the use has opted out to
        if type(layer) in type_ignore or index in index_ignore:
            continue

        # Do no render the SpacingDummyLayer, just increase the pointer
        if type(layer) == SpacingDummyLayer:
            current_z += layer.spacing
            continue

        layer_type = type(layer)

        if layer_type not in layer_types:
            layer_types.append(layer_type)

        x = min_xy
        y = min_xy
        z = min_z

        if hasattr(layer, 'output_shape'):
            output_shape = layer.output_shape
        else:
            output_shape = layer.output.shape
        
        if isinstance(output_shape, tuple):
            shape = output_shape
        elif isinstance(output_shape, list) and len(
                output_shape) == 1:  # drop dimension for non seq. models
            shape = output_shape[0]
        else:
            raise RuntimeError(f"not supported tensor shape {output_shape}")

        if len(shape) >= 4:
            x = min(max(shape[1] * scale_xy, x), max_xy)
            y = min(max(shape[2] * scale_xy, y), max_xy)
            z = min(max(self_multiply(shape[3:]) * scale_z, z), max_z)
        elif len(shape) == 3:
            x = min(max(shape[1] * scale_xy, x), max_xy)
            y = min(max(shape[2] * scale_xy, y), max_xy)
            z = min(max(self_multiply(shape[2:]) * scale_z, z), max_z)
        elif len(shape) == 2:
            if one_dim_orientation == 'x':
                x = min(max(shape[1] * scale_xy, x), max_xy)
            elif one_dim_orientation == 'y':
                y = min(max(shape[1] * scale_xy, y), max_xy)
            elif one_dim_orientation == 'z':
                z = min(max(shape[1] * scale_z, z), max_z)
            else:
                raise ValueError(f"unsupported orientation {one_dim_orientation}")
        else:
            raise RuntimeError(f"not supported tensor shape {layer.output_shape}")

        box = Box()

        box.de = 0
        if draw_volume and index not in index_2D:
            box.de = x / 3

        if x_off == -1:
            x_off = box.de / 2

        # top left coordinate
        box.x1 = current_z - box.de / 2
        box.y1 = box.de

        # bottom right coordinate
        box.x2 = box.x1 + z
        box.y2 = box.y1 + y

        box.fill = color_map.get(layer_type, {}).get('fill', color_wheel.get_color(layer_type))
        box.outline = color_map.get(layer_type, {}).get('outline', 'black')
        color_map[layer_type] = {'fill': box.fill, 'outline': box.outline}

        box.shade = shade_step
        boxes.append(box)
        layer_y.append(box.y2 - (box.y1 - box.de))

        # Update image bounds
        hh = box.y2 - (box.y1 - box.de)
        if hh > img_height:
            img_height = hh

        if box.x2 + box.de > max_right:
            max_right = box.x2 + box.de

        current_z += z + spacing

    # Generate image
    img_width = max_right + x_off + padding

    img = Image.new('RGBA', (int(ceil(img_width)), int(ceil(img_height))), background_fill)
    draw = aggdraw.Draw(img)

    # x, y correction (centering)
    for i, node in enumerate(boxes):
        y_off = (img.height - layer_y[i]) / 2
        node.y1 += y_off
        node.y2 += y_off

        node.x1 += x_off
        node.x2 += x_off

    # Correct x positions of reversed boxes
    if draw_reversed:
        for box in boxes:
            offset = box.de
            # offset = 0
            box.x1 = box.x1 + offset
            box.x2 = box.x2 + offset

    # Draw created boxes

    last_box = None

    if draw_reversed:
        for box in boxes:
            pen = aggdraw.Pen(get_rgba_tuple(box.outline))

            if last_box is not None and draw_funnel:
                # Top connection back
                draw.line([last_box.x2 - last_box.de, last_box.y1 - last_box.de,
                           box.x1 - box.de, box.y1 - box.de], pen)
                # Bottom connection back
                draw.line([last_box.x2 - last_box.de, last_box.y2 - last_box.de,
                           box.x1 - box.de, box.y2 - box.de], pen)

            last_box = box

        last_box = None

        for box in reversed(boxes):
            pen = aggdraw.Pen(get_rgba_tuple(box.outline))

            if last_box is not None and draw_funnel:
                # Top connection front
                draw.line([last_box.x1, last_box.y1,
                           box.x2, box.y1], pen)

                # Bottom connection front
                draw.line([last_box.x1, last_box.y2,
                           box.x2, box.y2], pen)

            box.draw(draw, draw_reversed=True)

            last_box = box
    else:
        for box in boxes:
            pen = aggdraw.Pen(get_rgba_tuple(box.outline))

            if last_box is not None and draw_funnel:
                draw.line([last_box.x2 + last_box.de, last_box.y1 - last_box.de,
                           box.x1 + box.de, box.y1 - box.de], pen)
                draw.line([last_box.x2 + last_box.de, last_box.y2 - last_box.de,
                           box.x1 + box.de, box.y2 - box.de], pen)

                draw.line([last_box.x2, last_box.y2,
                           box.x1, box.y2], pen)

                draw.line([last_box.x2, last_box.y1,
                           box.x1, box.y1], pen)

            box.draw(draw, draw_reversed=False)

            last_box = box

    draw.flush()

    # Create layer color legend
    if legend:
        if font is None:
            font = ImageFont.load_default()

        if hasattr(font, 'getsize'):
            text_height = font.getsize("Ag")[1]
        else:
            text_height = font.getbbox("Ag")[3]
        cube_size = text_height

        de = 0
        if draw_volume:
            de = cube_size // 2

        patches = list()

        for layer_type in layer_types:
            label = layer_type.__name__
            if hasattr(font, 'getsize'):
                text_width = font.getsize(label)[0]
            else:
                text_width = font.getbbox(label)[2]
            label_patch_size = (cube_size + de + spacing + text_width, cube_size + de)
            # this only works if cube_size is bigger than text height

            img_box = Image.new('RGBA', label_patch_size, background_fill)
            img_text = Image.new('RGBA', label_patch_size, (0, 0, 0, 0))
            draw_box = aggdraw.Draw(img_box)
            draw_text = ImageDraw.Draw(img_text)

            box = Box()
            box.x1 = cube_size
            box.x2 = box.x1 + cube_size
            box.y1 = de
            box.y2 = box.y1 + cube_size
            box.de = de
            box.shade = shade_step
            box.fill = color_map.get(layer_type, {}).get('fill', "#000000")
            box.outline = color_map.get(layer_type, {}).get('outline', "#000000")
            box.draw(draw_box, draw_reversed)

            text_x = box.x2 + box.de + spacing
            text_y = (label_patch_size[1] - text_height) / 2  # 2D center; use text_height and not the current label!
            draw_text.text((text_x, text_y), label, font=font, fill=font_color)

            draw_box.flush()
            img_box.paste(img_text, mask=img_text)
            patches.append(img_box)

        legend_image = linear_layout(patches, max_width=img.width, max_height=img.height, padding=padding,
                                     spacing=spacing,
                                     background_fill=background_fill, horizontal=True)
        img = vertical_image_concat(img, legend_image, background_fill=background_fill)

    if to_file is not None:
        img.save(to_file)

    return img
