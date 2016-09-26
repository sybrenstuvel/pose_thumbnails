'''This module does the actual work for the pose thumbnails addon.'''
# TODO:
#   - Clean match by index
#   - Make match by frame
#   - Add 'Remove thumbnail operator'
#   - Refresh/Sanitize button to refresh everything thoroughly
#   - Update label when renaming a pose
#   - Update all pose thumbnail suffixes when changing this in the preferences (update function?)
#   - Encoding issue with thumbnail labels? (Aaaaaah, shows weird) - Seems a bug in blender with 7 or more a's it getting weird. File bug report?
#   - Find better naming for add thumbnail(s)/add from dir. Add/update from dir? Add/update thumbnailS?

import os
import logging
import re
from collections import namedtuple
import difflib
if 'bpy' in locals():
    import importlib
    if 'prefs' in locals():
        importlib.reload(prefs)
else:
    from . import prefs
import bpy
import bpy.utils.previews
from bpy_extras.io_utils import ImportHelper


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
preview_collections = {}


def clean_pose_name(pose_name):
    '''Return the clean pose name, that is without thumbnail suffix.'''
    user_prefs = bpy.context.user_preferences
    addon_prefs = user_prefs.addons[__package__].preferences
    pose_thumbnail_suffix = addon_prefs.pose_thumbnail_suffix
    if pose_name.endswith(pose_thumbnail_suffix):
        return pose_name[:-len(pose_thumbnail_suffix)]
    else:
        return pose_name


def suffix_pose_name(pose_name):
    '''Return the pose name with the thumbnail suffix.'''
    user_prefs = bpy.context.user_preferences
    addon_prefs = user_prefs.addons[__package__].preferences
    pose_thumbnail_suffix = addon_prefs.pose_thumbnail_suffix
    if pose_name.endswith(pose_thumbnail_suffix):
        return pose_name
    else:
        return ''.join((pose_name, pose_thumbnail_suffix))


def get_images_from_dir(directory, sort=True):
    '''Get all image files in the directory.'''
    valid_images = []
    image_extensions = ['.png', '.jpg', '.jpeg']
    for filename in os.listdir(directory):
        if os.path.splitext(filename)[-1].lower() in image_extensions:
            valid_images.append(filename)
    return sorted(valid_images)


def get_thumbnail_from_pose(pose):
    '''Get the thumbnail that belongs to the pose.

    Args:
        pose (pose_marker): a pose in the pose library

    Returns:
        thumbnail PropertyGroup
    '''
    if pose is None:
        return
    poselib = pose.id_data
    for thumbnail in poselib.pose_thumbnails.info:
        if thumbnail.frame == pose.frame:
            return thumbnail


def get_pose_from_thumbnail(thumbnail):
    '''Get the pose that belongs to the thumbnail.

    Args:
        thumbnail (PropertyGroup): thumbnail info of a pose

    Returns:
        pose_marker
    '''
    if thumbnail is None:
        return
    poselib = thumbnail.id_data
    for pose in poselib.pose_markers:
        if pose.frame == thumbnail.frame:
            return pose


def get_pose_index(pose):
    '''Get the index of the pose.'''
    poselib = pose.id_data
    return poselib.pose_markers.find(pose.name)


def get_thumbnail_index(thumbnail):
    '''Return the index of the pose of the thumbnail.'''
    poselib = thumbnail.id_data
    for i, posemarker in enumerate(poselib.pose_markers):
        if thumbnail.frame == posemarker.frame:
            return i


def get_no_thumbnail_path():
    '''Get the path to the 'no thumbnail' image.'''
    no_thumbnail_path = os.path.join(
        os.path.dirname(__file__),
        'thumbnails',
        'no_thumbnail.png',
        )
    return no_thumbnail_path


def get_no_thumbnail_image(pcoll):
    '''Return the 'no thumbnail' preview icon.'''
    no_thumbnail_path = get_no_thumbnail_path()
    no_thumbnail = pcoll.get('No Thumbnail') or pcoll.load(
        'No Thumbnail',
        no_thumbnail_path,
        'IMAGE',
        )
    return no_thumbnail


def add_no_thumbnail_to_pose(pose):
    '''Add info with 'no thumbnail' image to the pose.'''
    poselib = pose.id_data
    no_thumbnail = poselib.pose_thumbnails.info.add()
    no_thumbnail.name = pose.name
    no_thumbnail.index = get_pose_index(pose)
    no_thumbnail.frame = pose.frame
    no_thumbnail.filepath = get_no_thumbnail_path()
    return no_thumbnail


def sort_thumbnails(poselib):
    '''Return the thumbnail info of a pose library sorted by pose index.

    If a pose doesn't have a thumbnail return the 'no thumbnail' image.

    Args:
        poselib (pose library): The pose library for which to get the thumbnails.

    Returns:
        list: the sorted pose thumbnail info
    '''
    pcoll = preview_collections['pose_library']
    for pose in poselib.pose_markers:
        # yield get_thumbnail_from_pose(pose) or add_no_thumbnail_to_pose(pose)
        thumbnail = get_thumbnail_from_pose(pose)
        if thumbnail:
            yield thumbnail


def get_enum_items(thumbnails, pcoll):
    '''Return the enum items for the thumbnail previews.'''
    for thumbnail in thumbnails:
        image = pcoll.get(thumbnail.filepath)
        if not image:
            image_path = os.path.normpath(bpy.path.abspath(thumbnail.filepath))
            if not os.path.isfile(image_path):
                image = get_no_thumbnail_image(pcoll)
            else:
                image = pcoll.load(
                    thumbnail.filepath,
                    image_path,
                    'IMAGE',
                    )
        yield ((
            str(thumbnail.frame),
            thumbnail.name,
            '',
            image.icon_id,
            thumbnail.index
            ))


def get_pose_thumbnails(self, context):
    '''Get the pose thumbnails and add them to the preview collection.'''
    poselib = context.object.pose_library
    if (context is None or
        not poselib.pose_markers or
        not poselib.pose_thumbnails.info):
            return []
    pcoll = preview_collections['pose_library']
    sorted_thumbnails = sort_thumbnails(poselib)
    enum_items = get_enum_items(
        sorted_thumbnails,
        pcoll,
        )
    pcoll.pose_thumbnails = enum_items
    return pcoll.pose_thumbnails


def update_pose(self, context):
    '''Callback when the enum property is updated (e.g. the index of the active
       item is changed).

    Args:
        self (pose library)
        context (blender context = bpy.context)

    Returns:
        None
    '''
    pose_frame = int(self.thumbnails)
    poselib = self.id_data
    for i, pose_marker in enumerate(poselib.pose_markers):
        if pose_marker.frame == pose_frame:
            bpy.ops.poselib.apply_pose(pose_index=i)
            logger.debug("Applying pose from pose marker '%s' (frame %s)" % (pose_marker.name, pose_frame))
            break


def pose_thumbnails_draw(self, context):
    '''Draw the thumbnail enum in the Pose Library panel.'''
    if not context.object.pose_library.pose_markers:
        return
    # user_prefs = context.user_preferences
    # addon_prefs = user_prefs.addons[__package__].preferences
    # show_labels = addon_prefs.show_labels
    poselib = context.object.pose_library
    thumbnail_ui_settings = poselib.pose_thumbnails.ui_settings
    show_labels = thumbnail_ui_settings.show_labels
    layout = self.layout
    col = layout.column(align=True)
    col.template_icon_view(
        poselib.pose_thumbnails,
        'thumbnails',
        show_labels=show_labels,
        )
    col.prop(thumbnail_ui_settings, 'show_labels', toggle=True)
    box = col.box()
    if thumbnail_ui_settings.advanced_settings:
        expand_icon = 'TRIA_DOWN'
    else:
        expand_icon = 'TRIA_RIGHT'
    box.prop(
        thumbnail_ui_settings,
        'advanced_settings',
        icon=expand_icon,
        toggle=True,
        )
    if thumbnail_ui_settings.advanced_settings:
        sub_col = box.column(align=True)
        if not poselib.pose_markers.active:
            return
        thumbnail = get_thumbnail_from_pose(poselib.pose_markers.active)
        if thumbnail and thumbnail.filepath != get_no_thumbnail_path():
            text = 'Update Thumbnail'
        else:
            text = 'Add Thumbnail'
        sub_col.operator(AddPoseThumbnail.bl_idname, text=text)
        sub_col.operator(AddPoseThumbnailsFromDir.bl_idname)


def pose_thumbnails_options_draw(self, context):
    '''Draw the thumbnail 'advanced' options in the Pose Library panel.'''
    if not context.object.pose_library.pose_markers:
        return
    user_prefs = context.user_preferences
    addon_prefs = user_prefs.addons[__package__].preferences
    poselib = context.object.pose_library
    layout = self.layout
    col = layout.column(align=True)
    # box = layout.box()
    # col = box.column(align=True)
    thumbnail_ui_settings = poselib.pose_thumbnails.ui_settings
    if thumbnail_ui_settings.advanced_settings:
        expand_icon = 'TRIA_DOWN'
    else:
        expand_icon = 'TRIA_RIGHT'
    col.prop(
        thumbnail_ui_settings,
        'advanced_settings',
        icon=expand_icon,
        toggle=True,
        )
    if thumbnail_ui_settings.advanced_settings:
        col.label(text='Advanced Settings')
        # col.label(text="General:")
        # row = col.row(align=True)
        # row = col.split(.5, align=True)


class AddPoseThumbnail(bpy.types.Operator, ImportHelper):
    '''Add a thumbnail to a pose from a pose library.'''
    bl_idname = 'poselib.add_thumbnail'
    bl_label = 'Add thumbnail'
    # bl_options = {'PRESET', 'UNDO'}

    filename_ext = '.jpg;.jpeg;.png'
    filter_glob = bpy.props.StringProperty(
        default='*.jpg;*.jpeg;*.png',
        options={'HIDDEN'},
        )

    use_relative_path = bpy.props.BoolProperty(
        name='Relative Path',
        description='Select the file relative to the blend file',
        default=True,
        )

    def execute(self, context):
        if not self.use_relative_path:
            filepath = self.filepath
        else:
            filepath = bpy.path.relpath(self.filepath)
        poselib = context.object.pose_library
        active_posemarker = poselib.pose_markers.active
        active_posemarker_index = poselib.pose_markers.active_index
        pose_name = active_posemarker.name
        name = clean_pose_name(pose_name)
        active_posemarker.name = suffix_pose_name(pose_name)
        thumbnail = (get_thumbnail_from_pose(active_posemarker) or
                     poselib.pose_thumbnails.info.add())
        thumbnail.name = name
        thumbnail.index = active_posemarker_index
        thumbnail.frame = active_posemarker.frame
        thumbnail.filepath = filepath
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, 'use_relative_path')


class AddPoseThumbnailsFromDir(bpy.types.Operator, ImportHelper):
    '''Add thumbnails from a directory to poses from a pose library.'''
    bl_idname = 'poselib.add_thumbnails_from_dir'
    bl_label = 'Add thumbnails from directory'
    bl_options = {'PRESET', 'UNDO'}

    directory = bpy.props.StringProperty(
        maxlen=1024,
        subtype='DIR_PATH',
        options={'HIDDEN', 'SKIP_SAVE'},
        )
    files = bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},
        )
    filename_ext = '.jpg;.jpeg;.png'
    filter_glob = bpy.props.StringProperty(
        default='*.jpg;*.jpeg;*.png',
        options={'HIDDEN'},
        )
    map_method_items = (
            ('NAME', 'Name', 'Map the files to the names of the poses.'),
            ('INDEX', 'Index', 'Map the files to the order of the poses (numbering the image files makes sense!)'),
            ('FRAME', 'Frame', 'Map the files to the order of the frame number of the poses (advanced and probably not so useful option).'),
            )
    map_method = bpy.props.EnumProperty(
        name='Match by',
        description='Match the thumbnail images to the poses by using this method',
        items=map_method_items,
        )
    overwrite_existing = bpy.props.BoolProperty(
        name='Overwrite existing',
        description='Overwrite existing thumbnails of the poses.',
        default=True,
        )
    cutoff = bpy.props.FloatProperty(
        name='Fuzzyness',
        description='Fuzzyness of the matching (0 = exact match, 1 = everything).',
        min=0.0,
        max=1.0,
        default=0.4,
        )
    match_by_number = bpy.props.BoolProperty(
        name='Match by number',
        description='If the filenames start with a number, match the number to the pose index.',
        default=False,
        )
    start_number = bpy.props.IntProperty(
        name='Start number',
        description='The image number to match to the first pose.',
        default=1,
        )
    use_relative_path = bpy.props.BoolProperty(
        name='Relative Path',
        description='Select the file relative to the blend file',
        default=True,
        )

    def get_images_from_dir(self):
        '''Get all image files from a directory.'''
        directory = self.directory
        files = [f.name for f in self.files]
        if files and not files[0]:
            image_files = os.listdir(directory)
        else:
            image_files = files
        for image_file in sorted(image_files):
            ext = os.path.splitext(image_file)[-1].lower()
            if ext and ext in self.filename_ext:
                image_path = os.path.join(directory, image_file)
                if self.use_relative_path:
                    yield bpy.path.relpath(image_path)
                else:
                    yield image_path

    def create_thumbnail(self, index, pose, image):
        '''Create or update the thumbnail for a pose.'''
        if not self.overwrite_existing and get_thumbnail_from_pose(pose):
            return
        poselib = self.poselib
        name = clean_pose_name(pose.name)
        pose.name = suffix_pose_name(pose.name)
        thumbnail = (get_thumbnail_from_pose(pose) or
                     poselib.pose_thumbnails.info.add())
        thumbnail.name = name
        thumbnail.index = index
        thumbnail.frame = pose.frame
        thumbnail.filepath = image

    def get_numbered_images(self):
        '''Return a named tuple with (index, image) for self.image_files.

        Check if the filename starts with a number, if so, that is the index,
        if not, skip the image.
        '''
        # TODO: remove double indices. Can be caused by filenames like:
        #       009-pose.jpg, 00009-pose.jpg, etc.
        IndexImage = namedtuple('IndexImage', ['number', 'image'])
        numbered_images = []
        for image in self.image_files:
            basename = os.path.basename(image)
            match = re.match(r'^([0-9]+).*', basename)
            if match:
                number = int(match.groups()[0])
                numbered_image = IndexImage(number, image)
                numbered_images.append(numbered_image)
        return numbered_images

    def match_thumbnails_by_name(self):
        '''Assign the thumbnail by trying to match the pose name with a file name.'''
        poselib = self.poselib
        thumbnails_info = poselib.pose_thumbnails.info
        image_files = self.image_files
        match_dict = {os.path.splitext(os.path.basename(f))[0]: f for f in image_files}
        for i, pose in enumerate(poselib.pose_markers):
            match = difflib.get_close_matches(
                clean_pose_name(pose.name),
                match_dict.keys(),
                n=3,
                cutoff=1.0 - self.cutoff,
                )
            if match:
                thumbnail_image = match_dict[match[0]]
                self.create_thumbnail(i, pose, thumbnail_image)

    def match_thumbnails_by_index(self):
        '''Map the thumbnail images to the index of the poses.'''
        poselib = self.poselib
        thumbnails_info = self.poselib.pose_thumbnails.info
        image_files = self.image_files
        start_number = self.start_number
        if self.match_by_number:
            numbered_images = self.get_numbered_images()
            if not numbered_images:
                return
            for i, pose in enumerate(poselib.pose_markers):
                if i + start_number == numbered_images[0].number:
                    image = numbered_images.pop(0).image
                    self.create_thumbnail(i, pose, image)
        else:
            for i, (pose, image) in enumerate(zip(poselib.pose_markers, image_files)):
                self.create_thumbnail(i, pose, image)

    def match_thumbnails_by_frame(self):
        return

    def match_thumbnails(self):
        '''Try to match the image files to the poses.'''
        map_method = self.map_method
        if map_method == 'NAME':
            self.match_thumbnails_by_name()
        elif map_method == 'INDEX':
            self.match_thumbnails_by_index()
        else:
            self.match_thumbnails_by_frame()

    def execute(self, context):
        self.poselib = context.object.pose_library
        self.image_files = self.get_images_from_dir()
        self.match_thumbnails()

        # active_posemarker = poselib.pose_markers.active
        # active_posemarker_index = poselib.pose_markers.active_index
        # name = clean_pose_name(active_posemarker.name)
        # active_posemarker.name = suffix_pose_name(active_posemarker.name)
        # thumbnail = (get_thumbnail_from_pose(active_posemarker) or
        #              poselib.pose_thumbnails.info.add())
        # thumbnail.name = name
        # thumbnail.index = active_posemarker_index
        # thumbnail.frame = active_posemarker.frame
        # thumbnail.filepath = filepath
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        box = col.box()
        box.label(text='Map method')
        row = box.row()
        row.prop(self, 'map_method', expand=True)
        box.prop(self, 'overwrite_existing')
        if self.map_method == 'NAME':
            box.prop(self, 'cutoff')
        if self.map_method == 'INDEX':
            box.prop(self, 'match_by_number')
            if self.match_by_number:
                box.prop(self, 'start_number')
        col.separator()
        col.prop(self, 'use_relative_path')


class PoselibThumbnails(bpy.types.PropertyGroup):
    '''A property to hold the thumbnail info for a pose.'''
    name = bpy.props.StringProperty(
        name='Pose name',
        description='The name of the pose marker.',
        default='',
        )
    index = bpy.props.IntProperty(
        name='Pose index',
        description='The index of the pose marker.',
        default=-1,
        )
    frame = bpy.props.IntProperty(
        name='Pose frame',
        description='The frame of the pose marker.',
        default=-1,
        )
    filepath = bpy.props.StringProperty(
        name='Thumbnail path',
        description='The file path of the thumbnail image.',
        default='',
        subtype='FILE_PATH',
        )


class PoselibThumbnailsOptions(bpy.types.PropertyGroup):
    '''A property to hold the option info for the thumbnail UI.'''
    advanced_settings = bpy.props.BoolProperty(
        name='Thumbnail creation',
        default=False,
        )
    show_labels = bpy.props.BoolProperty(
        name='Show labels',
        default=True,
        )


class PoselibThumbnailsInfo(bpy.types.PropertyGroup):
    '''A collection property for all thumbnail related properties.'''
    info = bpy.props.CollectionProperty(
        type=PoselibThumbnails)
    thumbnails = bpy.props.EnumProperty(
        items=get_pose_thumbnails,
        update=update_pose,
        )
    ui_settings = bpy.props.PointerProperty(
        type=PoselibThumbnailsOptions,
        )


def register():
    '''Register all pose thumbnail related things.'''
    bpy.types.Action.pose_thumbnails = bpy.props.PointerProperty(
        type=PoselibThumbnailsInfo)
    # bpy.types.Action. = bpy.props.PointerProperty(type=jasperge_tools.JaspergeToolsSettings)

    bpy.types.DATA_PT_pose_library.prepend(pose_thumbnails_draw)
    # bpy.types.DATA_PT_pose_library.append(pose_thumbnails_options_draw)

    pcoll = bpy.utils.previews.new()
    pcoll.pose_thumbnails = ()
    preview_collections['pose_library'] = pcoll


def unregister():
    '''Unregister all pose thumbnails related things.'''
    bpy.types.DATA_PT_pose_library.remove(pose_thumbnails_draw)
    # bpy.types.DATA_PT_pose_library.remove(pose_thumbnails_options_draw)
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()

    del bpy.types.Action.pose_thumbnails
