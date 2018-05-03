class Rect(object):
    __slots__ = (
        'top_left',
        'size'
    )

    def __init__(self, top_left=(0, 0), size=(0, 0)):
        self.top_left = top_left
        self.size = size

    @property
    def x(self):
        return self.top_left[0]

    @property
    def y(self):
        return self.top_left[1]

    @property
    def width(self):
        return self.size[0]

    @property
    def height(self):
        return self.size[1]

    @property
    def top(self):
        return self.y

    @property
    def left(self):
        return self.x

    @property
    def right(self):
        return self.left + self.width

    @property
    def bottom(self):
        return self.top + self.height

    def contains(self, other):
        return other.width <= self.width and other.height <= self.height

    @property
    def area(self):
        return self.width * self.height

    def __repr__(self):
        return '{}({}, {}, {}, {})'.format(self.__class__.__name__, self.left, self.top, self.width, self.height)


class Node(Rect):
    __slots__ = (
        'top_left',
        'size',
        'bucket',
        'small_child',
        'big_child'
    )

    def __init__(self, top_left=(0, 0), size=(0,0)):
        super().__init__(top_left, size)
        self.bucket = None
        self.small_child = None
        self.big_child = None

    def insert(self, node):
        # Recursive case
        if self.bucket:
            return self.small_child.insert(node) or self.big_child.insert(node)

        # Is this node large enough to contain target node
        if not self.contains(node):
            return None

        self.bucket = node
        self.bucket.top_left = self.top_left

        # Partition space into two
        """
        if node.width < node.height:
            self.small_child = Node((self.left, node.bottom), (node.width, self.height - node.height))
            self.big_child = Node((node.right, self.top), (self.width - node.width, self.height))

        else:
            self.small_child = Node((node.right, self.top), (self.width - node.width, node.height))
            self.big_child = Node((self.left, node.bottom), (self.width, self.height - node.height))
        """

        child_0 = Node((self.left, node.bottom), (node.width, self.height - node.height))
        child_1 = Node((node.right, self.top), (self.width - node.width, self.height))
        child_2 = Node((node.right, self.top), (self.width - node.width, node.height))
        child_3 = Node((self.left, node.bottom), (self.width, self.height - node.height))

        if max(child_0.area, child_1.area) > max(child_2.area, child_3.area):
            self.small_child = child_0
            self.big_child = child_1

        else:
            self.small_child = child_2
            self.big_child = child_3

        return self.bucket.top_left


from PIL import Image
import glob
import math
import os

glob_pattern = '/Users/Joshua/Games/QUAKE/id1/wads/id/*.png'
#glob_pattern = '/Users/Joshua/Desktop/tiles/*.png'
images_paths = [g for g in glob.glob(glob_pattern)]
images = [Image.open(file) for file in images_paths if os.path.getsize(file)]

#images = sorted(images, key=lambda i: i.width * i.height, reverse=True)
#images = sorted(images, key=lambda i: min(i.width, i.height), reverse=True)
images = sorted(images, key=lambda i: min(i.width, i.height) * i.width * i.height, reverse=True)

area = sum([i.width * i.height for i in images])
side = int(math.sqrt(area))
np2 = 1<<(side - 1).bit_length()

size = np2, np2
n = Node(size=size)

rects = [Rect(size=image.size) for image in images]
print('Packing {} images.'.format(len(rects)))
offsets = [n.insert(rect) for rect in rects]
print('Successfully packed {} images.'.format(len([o for o in offsets if o])))

sheet = Image.new('RGBA', size)
fill_color = 0, 255 , 255
sheet.paste(fill_color, [0, 0, *size])

for image_index, image in enumerate(images):
    if not offsets[image_index]:
        continue

    offset = offsets[image_index]
    sheet.paste(image, offset)

sheet.show()

print()