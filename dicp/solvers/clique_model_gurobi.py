from collections import defaultdict
from itertools import product
from gurobipy import GRB, Model, quicksum as sum


class CliqueModelGurobi(object):
    '''Transformed set packing model over maximal cliques'''
    _slug = 'clique-model-gurobi'

    def __init__(self, time=None):
        self.time = time  # in minutes

    def slug(self):
        return CliqueModelGurobi._slug

    def solve(self, problem, saver):
        # Construct model.
        self.problem = problem

        # Do recursive maximal clique detection.
        self.clique_data = clique_data = problem.cliques()
        self.model = model = Model()
        if self.time is not None:
            model.params.TimeLimit = 60 * int(self.time)

        # Each image needs to run all its commands. This keep track of
        # what variables run each command for each image.
        self.by_img_cmd = by_img_cmd = defaultdict(list)

        # Objective is the total cost of all the commands we run.
        self._obj = []

        # x[i,c] = 1 if image i incurs the cost of command c directly
        self.x = x = {}
        for img, cmds in problem.images.items():
            for cmd in cmds:
                name = 'x[%s,%s]' % (img, cmd)
                x[name] = v = model.addVar(vtype=GRB.BINARY, name=name)
                self._obj.append(problem.commands[cmd] * v)
                by_img_cmd[img, cmd].append(v)

        # cliques[i] = 1 if clique i is used, 0 otherwise
        self.cliques = {}
        self._update(clique_data)

        # Each image has to run each of its commands.
        for img_cmd, vlist in by_img_cmd.items():
            self.model.addConstr(sum(vlist) == 1)

        model.setObjective(sum(self._obj), GRB.MINIMIZE)
        model.optimize()  # lambda *args: self._callback(saver, *args))

        # TODO: callback
        # Translate the output of this to a schedule.
        schedule = defaultdict(list)
        self._translate(schedule, clique_data)
        for name, v in x.items():
            img, cmd = name.replace('x[', '').replace(']', '').split(',')
            if v.x > 0.5:
                schedule[img].append(cmd)
        saver(schedule)

    def _update(self, clique_data, parent=None):
        for c in clique_data['cliques']:
            self.cliques[c['name']] = v = self.model.addVar(
                vtype=GRB.BINARY,
                name=c['name']
            )
            self.model.update()

            for img, cmd in product(c['images'], c['commands']):
                self.by_img_cmd[img, cmd].append(v)

            self._obj.append(c['time'] * v)

            if parent is not None:
                self.model.addConstr(v <= self.cliques[parent['name']])

            for child in c['children']:
                self._update(child, c)

        for inter in clique_data['intersections']:
            self.model.addConstr(sum(self.cliques[i] for i in inter) <= 1)

    def _translate(self, schedule, data):
        for c in data['cliques']:
            if self.cliques[c['name']].x > 0.5:
                for img, cmd in product(c['images'], c['commands']):
                    schedule[img].append(cmd)
                for child in c['children']:
                    self._translate(schedule, child)
