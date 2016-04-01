from collections import defaultdict
from gurobipy import GRB, Model, quicksum as sum
from itertools import combinations, product
import time


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

        for iteration in range(100):
            print '[%02d / %s]' % (iteration, time.asctime())

            cmds_dual, img_cmd_duals, clique_inter_duals = self._master()
            done = True

            new_sigs = self._subproblem1(cmds_dual, img_cmd_duals) + \
                self._subproblem2(clique_inter_duals)  # + \
            # self._subproblem3(cliques_on)

            for sig in new_sigs:
                print sig
                imgs, cmds = sig
                if imgs and cmds and sig not in self.cliques:
                    done = False
                    for img in imgs:
                        self.intersections[img].append(sig)

                    self.cliques.add(sig)
                    for img, cmd in product(imgs, cmds):
                        self.img_cmd_to_cliques[img, cmd].append(sig)

            if done:
                for foo in self._master(final=True):
                    if len(foo[0]) > 1:
                        print foo
                print '\ncliques'
                for c in sorted(self.cliques):
                    if len(c[0]) > 1:
                        print c
                break

            print

    def _master(self, final=False):
        model = Model()
        model.setParam('OutputFlag', False)
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

        # Max number of (image, command) pairs
        total_commands_constraint = model.addConstr(
            sum(len(sig[0]) * len(sig[1]) * x[sig] for sig in self.cliques) <= self.problem.num_pairs
        )

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
        clique_inter_constraints = {}
        for sig1, sig2 in combinations(self.cliques, 2):
            sig1, sig2 = tuple(sorted([sig1, sig2]))
            imgs1, cmds1 = sig1
            imgs2, cmds2 = sig2
            imgs1 = set(imgs1)
            imgs2 = set(imgs2)
            # cmds1 = set(cmds1)
            # cmds2 = set(cmds2)

            if imgs1.intersection(imgs2) and imgs1 - imgs2 and imgs2 - imgs1:
                clique_inter_constraints[sig1, sig2] = model.addConstr(x[sig1] + x[sig2] <= 1)
                # if not cmds1.intersection(cmds2):
                #     model.addConstr(x[sig1] + x[sig2] <= 1)

        model.setObjective(sum(obj), GRB.MINIMIZE)
        model.optimize()

        if final:
            print 'obj: %.02f' % model.objVal
            return [c for c in self.cliques if x[c].x > 0.5]
        else:
            img_cmd_duals = defaultdict(float)
            clique_inter_duals = defaultdict(float)

            for k, c in sorted(img_cmd_constraints.items()):
                if c.pi:
                    print '(img/cmd dual) {%s, %s} = %.02f' % (k[0], k[1], c.pi)
                img_cmd_duals[k] = c.pi

            for k, c in sorted(clique_inter_constraints.items()):
                if c.pi:
                    print '(clique/inter dual) {%s, %s} = %.02f' % (k[0], k[1], c.pi)
                clique_inter_duals[k] = c.pi

            return total_commands_constraint.pi, img_cmd_duals, clique_inter_duals

    def _subproblem1(self, cmds_dual, img_cmd_duals):
        model = Model()
        model.setParam('OutputFlag', False)
        obj = []

        imgs = {}
        for i in self.problem.images:
            imgs[i] = v = model.addVar(vtype=GRB.BINARY)

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

        model.setObjective(sum(obj) - cmds_dual, GRB.MINIMIZE)
        model.optimize()

        if model.objVal < 0:
            images = tuple(sorted([i for i, v in imgs.items() if v.x > 0.5]))
            commands = tuple(sorted([c for c, v in cmds.items() if v.x > 0.5]))
            return [(images, commands)]

        return []

    def _subproblem2(self, clique_inter_duals):
        sigs = []

        for (sig1, sig2), dual in clique_inter_duals.items():
            if not dual:
                continue

            imgs1, cmds1 = sig1
            imgs2, cmds2 = sig2

            imgs1, cmds1 = set(imgs1), set(cmds1)
            imgs2, cmds2 = set(imgs2), set(cmds2)

            inter_cmds = cmds1.intersection(cmds2)
            if inter_cmds:
                if len(imgs1) > 1:
                    sigs.append((tuple(sorted(imgs1.union(imgs2))), tuple(sorted(inter_cmds))))

                    cmds1_diff = cmds1 - inter_cmds
                    if cmds1_diff:
                        sigs.append((tuple(sorted(imgs1)), tuple(sorted(cmds1_diff))))

                if len(imgs2) > 1:
                    cmds2_diff = cmds2 - inter_cmds
                    if cmds2_diff:
                        sigs.append((tuple(sorted(imgs2)), tuple(sorted(cmds2_diff))))

            inter_imgs = imgs1.intersection(imgs2)
            if inter_imgs:
                if len(inter_imgs) > 1:
                    sigs.append((tuple(sorted(inter_imgs)), tuple(sorted(cmds1))))
                    sigs.append((tuple(sorted(inter_imgs)), tuple(sorted(cmds2))))

                imgs1_diff = imgs1 - inter_imgs
                if len(imgs1_diff) > 1:
                    sigs.append((tuple(sorted(imgs1_diff)), tuple(sorted(cmds1))))

                imgs2_diff = imgs2 - inter_imgs
                if imgs2_diff:
                    sigs.append((tuple(sorted(imgs2_diff)), tuple(sorted(cmds2))))

        return sigs

    def _subproblem3(self, clique_bound_duals):
        sigs = []
        return sigs
