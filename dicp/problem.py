from operator import itemgetter
import json
import random

class Problem(object):
    @staticmethod
    def generate(num_images, num_cmds, max_time):
        '''Generates a random instance of the DICP.'''
        img_fmt = '%%0%sd' % len(str(num_images))
        cmd_fmt = '%%0%sd' % len(str(num_cmds))

        # Each command has an expected amount of time it will take to execute.
        commands = {cmd_fmt % c: random.randint(1, max_time) for c in range(1, num_cmds+1)}

        # Each image is comprised of the commands required to construct it.
        images = {}
        for i in range(1, num_images+1):
            size = random.randint(1, num_cmds)
            images[img_fmt % i] = list(sorted(random.sample(commands, size)))

        return Problem(commands, images)

    @staticmethod
    def load(path):
        '''Loads an instance of the DICP from a json file.'''
        p = json.load(open(path))
        return Problem(p['commands'], p['images'])

    def __init__(self, commands, images):
        self.commands = commands
        self.images = images

    def save(self, path):
        '''Saves a DICP instance to a json file'''
        # json formatting doen't make it very human readable, so we do our own.
        with open(path, 'w') as fp:
            fp.write('{\n')
            fp.write('    "images": {\n')
            for j, (i, v) in enumerate(sorted(self.images.items(), key=itemgetter(0))):
                if j == len(self.images)-1:
                    end = '\n'
                else:
                    end = ',\n'
                fp.write(('        "%s": %r%s' % (i, v, end)).replace("'", '"'))
            fp.write('    },\n')

            fp.write('    "commands": {\n')
            for i, (c, v) in enumerate(sorted(self.commands.items(), key=itemgetter(0))):
                if i == len(self.commands)-1:
                    end = '\n'
                else:
                    end = ',\n'
                fp.write('        "%s": %d%s' % (c, v, end))
            fp.write('    }\n')
            fp.write('}\n')
