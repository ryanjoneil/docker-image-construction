from collections import defaultdict
from gurobipy import GRB, Model, quicksum as sum


class ColgenModelGurobi(object):
    '''Column Generation model'''
    _slug = 'colgen-model-gurobi'

    def __init__(self, time=None):
        self.time = time  # in minutes

    def slug(self):
        return ColgenModelGurobi._slug

    def solve(self, problem, saver):
        self.problem = problem

        # Starting cliques
        self.cliques = set()
        self.img_cmd_to_cliques = defaultdict(list)
        for img, cmds in problem.images.items():
            for cmd in cmds:
                sig = ((img,), (cmd,))
                self.cliques.add(sig)
                self.img_cmd_to_cliques[img, cmd].append(sig)

        while True:
            self._master()
            break

    def _master(self):
        model = Model()

        # Objective is the total cost of all the commands we run.
        obj = []

        # x[i,c] = 1 if clique c is used
        x = {}
        for clique in self.cliques:
            imgs, cmds = clique
            x[clique] = v = model.addVar()
            obj.append(sum(self.problem.commands[cmd] for cmd in cmds) * v)

        model.update()

        # Each image has to run each of its commands.
        for img, cmds in self.problem.images.items():
            for cmd in cmds:
                model.addConstr(sum(x[c] for c in self.img_cmd_to_cliques[img, cmd]) >= 1)

        model.setObjective(sum(obj), GRB.MINIMIZE)
        model.optimize()
