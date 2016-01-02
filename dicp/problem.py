from collections import OrderedDict, defaultdict
from itertools import combinations
from igraph import Graph
from operator import itemgetter
import json
import math
import networkx as nx
import numpy as np
import random

class Problem(object):
    @staticmethod
    def generate(num_images, num_cmds, max_time):
        '''Generates a random instance of the DICP.'''
        img_fmt = '%%0%sd' % len(str(num_images))
        cmd_fmt = '%%0%sd' % len(str(num_cmds))

        # Each command has an expected amount of time it will take to execute.
        commands = {
            cmd_fmt % c: int(math.ceil(np.random.exponential(max_time)))
            for c in range(1, num_cmds+1)
        }

        # Each image is comprised of the commands required to construct it.
        images = {}
        for i in range(1, num_images+1):
            size = np.random.poisson(num_cmds/4)
            images[img_fmt % i] = list(sorted(random.sample(commands, size)))

        return Problem(commands, images)

    @staticmethod
    def load(path):
        '''Loads an instance of the DICP from a json file.'''
        p = json.load(open(path))
        return Problem(p['commands'], p['images'])

    def __init__(self, commands, images):
        self.commands = OrderedDict(sorted(commands.items(), key=itemgetter(0)))
        self.images = OrderedDict(sorted(images.items(), key=itemgetter(0)))

    def save(self, path):
        '''Saves a DICP instance to a json file'''
        # json formatting doen't make it very human readable, so we do our own.
        with open(path, 'w') as fp:
            fp.write('{\n')
            fp.write('    "images": {\n')
            for j, (i, v) in enumerate(self.images.items()):
                if j == len(self.images)-1:
                    end = '\n'
                else:
                    end = ',\n'
                fp.write(('        "%s": %r%s' % (i, v, end)).replace("'", '"'))
            fp.write('    },\n')

            fp.write('    "commands": {\n')
            for i, (c, v) in enumerate(self.commands.items()):
                if i == len(self.commands)-1:
                    end = '\n'
                else:
                    end = ',\n'
                fp.write('        "%s": %d%s' % (c, v, end))
            fp.write('    }\n')
            fp.write('}\n')

    @property
    def all_stages(self):
        '''Property providing all stages in the problem.'''
        try:
            return self._all_stages
        except AttributeError:
            self._all_stages = range(1, len(self.commands)+1)
            return self._all_stages

    @property
    def stages(self):
        '''Property mapping image names to a iterables of their stages.'''
        try:
            return self._stages
        except AttributeError:
            self._stages = {i: range(1, len(v)+1) for i, v in self.images.items()}
            return self._stages

    @property
    def shared_stages(self):
        '''Property mapping ordered image pairs to shared stages.'''
        try:
            return self._shared_stages
        except AttributeError:
            self._shared_stages = {k: range(1,len(v)+1) for k, v in self.shared_cmds.items()}
            return self._shared_stages

    @property
    def shared_cmds(self):
        '''Property mapping ordered image pairs to shared command sets.'''
        try:
            return self._shared_cmds
        except AttributeError:
            self._shared_cmds = {}
            images = self.images.items()
            for i, (img_i, cmds_i) in enumerate(images):
                for img_j, cmds_j in images[i+1:]:
                    self._shared_cmds[img_i,img_j] = set(cmds_i) & set(cmds_j)
            return self._shared_cmds

    def cliques(self):
        '''Returns all maximal cliques with 2+ images & their intersections'''
        return self._cliques(self.images)

    def _cliques(self, images, prefix='c'):
        g = Graph()
        vertices = {}
        image_to_vert = {}
        cmd_to_vert = {}
        edges = []

        # All commands that are used in these images.
        commands = set()
        for cmds in images.values():
            commands.update(cmds)

        # Vertices are all images and all commands.
        idx = 0
        for i in images:
            vertices[idx] = 'image-%s' % i
            image_to_vert[i] = idx
            idx += 1
        for c in commands:
            vertices[idx] = 'cmd-%s' % c
            cmd_to_vert[c] = idx
            idx += 1

        g.add_vertices(vertices)

        # Add nodes for all images and connect them.
        for i1, i2 in combinations(images, 2):
            edges.append((image_to_vert[i1], image_to_vert[i2]))

        # Add nodes for all commands and connect them.
        for c1, c2 in combinations(commands, 2):
            edges.append((cmd_to_vert[c1], cmd_to_vert[c2]))

        # Connect images and commands that are related.
        for i, cmds in images.items():
            for c in cmds:
                edges.append((image_to_vert[i], cmd_to_vert[c]))

        g.add_edges(edges)

        # Find all maximal cliques. Filter out those with < 2 images.
        # Fix the image and command names.
        cliques = []
        num = 1
        for c in g.maximal_cliques(3):  # At least 2 images and 1 command
            imgs = set([
                vertices[x].replace('image-', '') for x in c
                if vertices[x].startswith('image-')
            ])
            cmds = set([
                vertices[x].replace('cmd-', '') for x in c
                if vertices[x].startswith('cmd-')
            ])
            if len(imgs) > 1 and cmds:
                total_time = sum(self.commands[c] for c in cmds)

                name = '%s%d' % (prefix, num)

                # Find all the child cliques of this clique.
                children = []
                if len(imgs) > 2:
                    new_images = {}
                    for img in imgs:
                        new_cmds = set(images[img]) - cmds
                        if new_cmds:
                            new_images[img] = new_cmds

                    if len(new_images) > 1:
                        children.append(self._cliques(new_images, prefix='%s_' % name))

                cliques.append({
                    'name':     '%s%d' % (prefix, num),
                    'time':     total_time,
                    'images':   imgs,
                    'commands': cmds,
                    'children': children
                })

                num += 1

        # Find intersections among them.
        by_img = defaultdict(set)
        for cl in cliques:
            for c in cl['images']:
                by_img[c].add(cl['name'])

        intersections = set()
        for x in by_img.values():
            if len(x) > 1:
                intersections.add(tuple(sorted(x)))

        return {'cliques': cliques, 'intersections': intersections}
