from collections import namedtuple

__all__ = ['KdRegionTree', 'KdRegionTreeError']


class Rect(object):
    __slots__ = (
        'top_left',
        '_size'
    )

    def __init__(self, top_left=(0, 0), size=(0, 0)):
        self.top_left = top_left
        self._size = size

    x = property(lambda self: self.top_left[0])
    y = property(lambda self: self.top_left[1])
    size = property(lambda self: self._size)
    width = property(lambda self: self._size[0])
    height = property(lambda self: self._size[1])
    top = property(lambda self: self.y)
    left = property(lambda self: self.x)
    right = property(lambda self: self.left + self.width)
    bottom = property(lambda self: self.top + self.height)
    area = property(lambda self: self.width * self.height)

    def contains(self, other):
        return other.width <= self.width and other.height <= self.height

    def __repr__(self):
        return '{}({}, {}, {}, {})'.format(self.__class__.__name__, self.left, self.top, self.width, self.height)


class Node(Rect):
    __slots__ = (
        'top_left',
        'size',
        'bucket',
        'left_child',
        'right_child'
    )

    def __init__(self, top_left=(0, 0), size=(0,0)):
        super().__init__(top_left, size)
        self.bucket = None
        self.left_child = None
        self.right_child = None

    def insert(self, node):
        # Recursive case
        if self.bucket:
            return self.left_child.insert(node) or self.right_child.insert(node)

        # Is this node large enough to contain target node
        if not self.contains(node):
            return None

        self.bucket = node
        self.bucket.top_left = self.top_left

        # Partition space such that the right child's area is maximized
        child_0 = Node((self.left, node.bottom), (node.width, self.height - node.height))
        child_1 = Node((node.right, self.top), (self.width - node.width, self.height))
        child_2 = Node((node.right, self.top), (self.width - node.width, node.height))
        child_3 = Node((self.left, node.bottom), (self.width, self.height - node.height))

        if max(child_0.area, child_1.area) > max(child_2.area, child_3.area):
            self.left_child = child_0
            self.right_child = child_1

        else:
            self.left_child = child_2
            self.right_child = child_3

        return self.bucket.top_left


class KdRegionTreeError(Exception):
    pass


class KdRegionTree(object):
    """Class for densely packing areas

    Example:
        atlas = KdRegionTree((100, 100))
        atlas.insert(Rect(size=10, 10))
    """

    def __init__(self, size):
        self._root = Node(size=size)

    def insert(self, element):
        """Inserts the given element into the tree

        Args:
            element: An object that represents an area. Must have 'size'
            attribute.

        Returns:
             A two-tuple representing the top-left coordinate of the inserted
             element.
        """

        if not hasattr(element, 'size'):
            raise KdRegionTreeError("Inserted element must have 'size' attribute.")

        if min(element.size) <= 0:
            raise KdRegionTreeError('Inserted element must have non-zero area')

        rect = Rect(size=element.size)

        return self._root.insert(rect)


PackResult = namedtuple('PackResult', ['atlas_size', 'offsets'])


class AtlasPacker(object):
    @staticmethod
    def pack(images, size=None):
        if not size:
            area = sum([i.width * i.height for i in images])
            side = 1 << (int(math.sqrt(area)) - 1).bit_length()
            size = side, side

        sorted_images = sorted(images, key=lambda i: min(i.size) * i.width * i.height, reverse=True)
        image_mapping = [images.index(i) for i in sorted_images]

        tree = KdRegionTree(size)
        offsets = [tree.insert(i) for i in sorted_images]
        offsets = [offsets[j] for j in image_mapping]

        return PackResult(size, offsets)


if __name__ == '__main__':
    from PIL import Image
    import glob
    import math
    import os

    glob_pattern = '/Users/Joshua/Games/QUAKE/id1/wads/id/*.png'
    #glob_pattern = '/Users/Joshua/Desktop/tiles/*.png'
    images_paths = [g for g in glob.glob(glob_pattern)]
    images = [Image.open(file) for file in images_paths if os.path.getsize(file)]

    # Sort using area weighted by shortest edge.
    # NOTE: This is not necessary but yields nicer (more dense) results.
    #images = sorted(images, key=lambda i: min(i.size) * i.width * i.height, reverse=True)

    # Calculate nearest power of two for atlas size
    area = sum([i.width * i.height for i in images])
    side = 1 << (int(math.sqrt(area)) - 1).bit_length()
    size = side, side

    # Pack images
    atlas = KdRegionTree(size)
    offsets = [atlas.insert(image) for image in images]

    size, offsets = AtlasPacker.pack(images)

    total_images = len(images)
    packed_images = len([o for o in offsets if o])
    print('Successfully packed {} of {} images.'.format(packed_images, total_images))

    # Create atlas image
    sheet = Image.new('RGBA', size)
    fill_color = 0, 255, 255
    sheet.paste(fill_color, [0, 0, *size])

    # Composite image
    for image_index, image in enumerate(images):
        if not offsets[image_index]:
            continue

        offset = offsets[image_index]
        sheet.paste(image, offset)

    sheet.show()
