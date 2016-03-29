from collections import defaultdict
from gurobipy import GRB, Model, quicksum as sum
from itertools import product


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

        # Start with no intersections
        self.intersections = defaultdict(list)

        while True:
            img_cmd_duals, img_inter_duals = self._master()
            sig = self._subproblem(img_cmd_duals, img_inter_duals)

            imgs, cmds = sig
            if imgs and cmds and sig not in self.cliques:
                for img in imgs:
                    self.intersections[img].append(sig)

                self.cliques.add(sig)
                for img, cmd in product(imgs, cmds):
                    self.img_cmd_to_cliques[img, cmd].append(sig)

            else:
                for foo in self._master(final=True):
                    print foo
                break

    def _master(self, final=False):
        model = Model()
        obj = []

        # x[i,c] = 1 if clique c is used
        x = {}
        for clique in self.cliques:
            imgs, cmds = clique
            if final:
                x[clique] = v = model.addVar(vtype=GRB.BINARY)
            else:
                x[clique] = v = model.addVar()
            obj.append(sum(self.problem.commands[cmd] for cmd in cmds) * v)

        model.update()

        # Each image has to run each of its commands.
        img_cmd_constraints = {}
        for img, cmds in self.problem.images.items():
            for cmd in cmds:
                vlist = [x[c] for c in self.img_cmd_to_cliques[img, cmd]]
                if final:
                    model.addConstr(sum(vlist) == 1)
                else:
                    img_cmd_constraints[img, cmd] = model.addConstr(sum(vlist) >= 1)

        # Cliques that intersect can only have one on
        img_inter_constraints = {}
        for img, inter in self.intersections.items():
            if len(inter) > 1:
                vlist = [x[c] for c in inter]
                img_inter_constraints[img] = model.addConstr(sum(vlist) <= 1)

        model.setObjective(sum(obj), GRB.MINIMIZE)
        model.optimize()

        if final:
            return [c for c in self.cliques if x[c].x > 0.5]
        else:
            img_cmd_duals = defaultdict(float)
            img_inter_duals = defaultdict(float)

            for k, c in img_cmd_constraints.items():
                img_cmd_duals[k] = c.pi

            for k, c in img_inter_constraints.items():
                img_inter_duals[k] = c.pi

            return img_cmd_duals, img_inter_duals

    def _subproblem(self, img_cmd_duals, img_inter_duals):
        model = Model()
        obj = []

        imgs = {}
        for i in self.problem.images:
            imgs[i] = v = model.addVar(vtype=GRB.BINARY)
            obj.append(-img_inter_duals[i] * v)

        cmds = {}
        for c, t in self.problem.commands.items():
            cmds[c] = v = model.addVar(vtype=GRB.BINARY)
            obj.append(t * v)

        y = {}
        for i, cs in self.problem.images.items():
            for c in self.problem.commands:
                y[i, c] = v = model.addVar(vtype=GRB.BINARY)
                obj.append(-img_cmd_duals[i, c] * v)

        model.update()

        model.addConstr(sum(imgs.values()) >= 2)
        model.addConstr(sum(cmds.values()) >= 1)

        for i, cs in self.problem.images.items():
            for c in self.problem.commands:
                if c in cs:
                    model.addConstr(y[i, c] <= imgs[i])
                    model.addConstr(y[i, c] <= cmds[c])
                    model.addConstr(y[i, c] >= imgs[i] + cmds[c] - 1)
                else:
                    model.addConstr(y[i, c] <= imgs[i])
                    model.addConstr(y[i, c] <= 0)
                    model.addConstr(y[i, c] >= imgs[i] + cmds[c] - 1)

        model.setObjective(sum(obj), GRB.MINIMIZE)
        model.optimize()

        if model.objVal < 0:
            images = tuple(sorted([i for i, v in imgs.items() if v.x > 0.5]))
            commands = tuple(sorted([c for c, v in cmds.items() if v.x > 0.5]))
            return images, commands

        return (), ()
