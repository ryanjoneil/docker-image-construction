class Clique(object):
    NEXT_ID = 1

    def __init__(self, problem, images, commands, parent=None):
        self.problem = problem
        self.images = tuple(sorted(images))
        self.commands = tuple(sorted(commands))
        self.images_set = set(self.images)
        self.commands_set = set(self.commands)
        self.parent = parent

        self.remaining = {}
        for i in self.images:
            if parent:
                cmds = parent.remaining[i] - self.commands_set
            else:
                cmds = set(self.problem.images[i]) - self.commands_set
            if cmds:
                self.remaining[i] = cmds

        self.remaining_commands = set()
        for cmds in self.remaining.values():
            self.remaining_commands = self.remaining_commands.union(cmds)

        self.id = Clique.NEXT_ID
        Clique.NEXT_ID += 1

    @property
    def cost(self):
        return sum(self.problem.commands[c] for c in self.commands)

    @property
    def size(self):
        return len(self.images) * len(self.commands)

    def __hash__(self):
        return hash((self.images, self.commands, hash(self.parent)))

    def __cmp__(self, other):
        return cmp(self.parent, other.parent) or cmp(self.images, other.images) or cmp(self.commands, other.commands)

    def __str__(self):
        self_str = '{%s, %s}' % (' '.join(map(str, self.images)), ' '.join(map(str, self.commands)))
        if self.parent:
            return '%s->%s' % (self.parent, self_str)
        return self_str

    __repr__ = __str__
