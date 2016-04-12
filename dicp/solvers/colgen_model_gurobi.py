from collections import defaultdict
from dicp.clique import Clique
from gurobipy import GRB, Model, quicksum
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
        self.img_to_cliques = defaultdict(list)  # cliques with >= 2 cmds
        for img, cmds in problem.images.items():
            for cmd in cmds:
                clique = Clique(problem, [img], [cmd])
                self.cliques.add(clique)
                self.img_cmd_to_cliques[img, cmd].append(clique)
                self.img_to_cliques[img].append(clique)

        for cmd, imgs in problem.images_by_command.items():
            if len(imgs) < 2:
                continue
            clique = Clique(problem, imgs, [cmd])
            self.cliques.add(clique)
            for img in imgs:
                self.img_cmd_to_cliques[img, cmd].append(clique)
                self.img_to_cliques[img].append(clique)

        for iteration in range(1000):
            print '[iteration %02d / %s]' % (iteration + 1, time.asctime())

            done = True
            self._master()
            for clique in self._subproblem():
                if clique is not None and clique not in self.cliques:
                    print '[new clique] %s' % clique

                    done = False
                    self.cliques.add(clique)
                    for img, cmd in product(clique.images, clique.commands):
                        self.img_cmd_to_cliques[img, cmd].append(clique)
                    for img in clique.images:
                        self.img_to_cliques[img].append(clique)

            if done:
                solution = self._master(final=True)

                print '\n[solution]'
                for clique in sorted(solution):
                    if len(clique.images) > 1:
                        print clique

                print '\n[cliques]'
                for clique in sorted(self.cliques):
                    if len(clique.images) > 1:
                        print clique
                break
            print

    def _master(self, final=False):
        self.img_cmd_duals = defaultdict(float)
        self.clique_inter_duals = defaultdict(float)

        model = Model()
        model.params.OutputFlag = False
        obj = []

        # x[i,c] = 1 if clique c is used
        x = {}
        for clique in self.cliques:
            if final:
                x[clique] = v = model.addVar(vtype=GRB.BINARY)
            else:
                x[clique] = v = model.addVar()
            obj.append(clique.cost * v)

        model.update()

        # Each image has to run each of its commands.
        img_cmd_constraints = {}
        for img, cmds in self.problem.images.items():
            for cmd in cmds:
                vlist = [x[c] for c in self.img_cmd_to_cliques[img, cmd]]
                if final:
                    model.addConstr(quicksum(vlist) == 1)
                else:
                    img_cmd_constraints[img, cmd] = model.addConstr(quicksum(vlist) >= 1)

        # Clique intersections
        clique_inter_constraints = {}
        for cliques in self.img_to_cliques.values():
            for c1, c2 in combinations(cliques, 2):
                c1, c2 = tuple(sorted([c1, c2]))
                if (c1, c2) in clique_inter_constraints:
                    continue

                disjoint_images = bool(c1.images_set - c2.images_set and c2.images_set - c1.images_set)
                overlapping_images = bool(c1.images_set.intersection(c2.images_set))
                overlapping_commands = bool(c1.commands_set.intersection(c2.commands_set))

                if disjoint_images or (overlapping_images and overlapping_commands):
                    clique_inter_constraints[c1, c2] = model.addConstr(x[c1] + x[c2] <= 1)

        model.setObjective(quicksum(obj), GRB.MINIMIZE)
        model.optimize()

        if final:
            print '\n[final master obj: %.02f]' % model.objVal
            return [c for c in self.cliques if x[c].x > 0.5]

        else:
            header = '     | %s' % (' '.join('% 6s' % c for c in self.problem.commands))
            print '-' * len(header)
            print header
            print '-' * len(header)
            for img in self.problem.images:
                duals = []
                for cmd in self.problem.commands:
                    try:
                        extra = img_cmd_constraints[img, cmd].pi
                        self.img_cmd_duals[img, cmd] = extra
                        duals.append(round(extra, 1) or '')
                    except KeyError:
                        duals.append('')
                print '% 4s | %s' % (img, ' '.join('% 6s' % d for d in duals))
            print '-' * len(header)

            for (c1, c2), c in clique_inter_constraints.items():
                if c.pi:
                    print '[clique/inter dual] %s | %s = %.02f' % (c1, c2, c.pi)
                self.clique_inter_duals[c1, c2] = c.pi

    def _subproblem(self):
        cliques = []

        model = Model()
        # model.params.OutputFlag = False
        model.params.LazyConstraints = True
        obj = []

        y = {}  # Do we resolve the intersection?
        yl = {}
        yi = {}
        yr = {}
        p = {}  # 1 if we turn on clique c
        q = defaultdict(dict)  # 1 if image i is run for clique c
        r = defaultdict(dict)  # 1 if we remove image i from clique c

        y_by_c = defaultdict(list)
        yl_by_c = defaultdict(list)
        yi_by_c = defaultdict(list)
        yr_by_c = defaultdict(list)

        for (c1, c2), pi in self.clique_inter_duals.items():
            y[c1, c2] = v = model.addVar(name='y_%s_%s' % (c1, c2), vtype=GRB.BINARY)
            obj.append(pi * v)

            y_by_c[c1].append(v)
            y_by_c[c2].append(v)

            yl[c1, c2] = v = model.addVar(name='yl_%s_%s' % (c1, c2), vtype=GRB.BINARY)
            yl_by_c[c1].append(v)
            yl_by_c[c2].append(v)

            yi[c1, c2] = v = model.addVar(name='yi_%s_%s' % (c1, c2), vtype=GRB.BINARY)
            yi_by_c[c1].append(v)
            yi_by_c[c2].append(v)

            yr[c1, c2] = v = model.addVar(name='yr_%s_%s' % (c1, c2), vtype=GRB.BINARY)
            yr_by_c[c1].append(v)
            yr_by_c[c2].append(v)

            for c in (c1, c2):
                if c not in p:
                    p[c] = v = model.addVar(name='p_%s' % c, vtype=GRB.BINARY)
                    obj.append(-c.cost * v)

                for i in c.images:
                    q[c][i] = v = model.addVar(name='q_%s_%s' % (c, i), vtype=GRB.BINARY)
                    dual = sum(self.img_cmd_duals[i, cmd] for cmd in c.commands)
                    obj.append(dual * v)

                for i in c1.images_set.intersection(c2.images_set):
                    r[c][i] = model.addVar(name='r_%s_%s' % (c, i), vtype=GRB.BINARY)

        model.update()
        for c, vs in y_by_c.items():
            for v in vs:
                model.addConstr(p[c] <= v)

        for c in y_by_c:
            for v, vl, vi, vr in zip(y_by_c[c], yl_by_c[c], yi_by_c[c], yr_by_c[c]):
                model.addConstr(v <= vl + vi + vr)
                model.addConstr(vl + vi + vr <= 1)

        for (c1, c2), vl in yl.items():
            for i in c1.images_set - c2.images_set:
                model.addConstr(vl <= r[c1][i])

        for (c1, c2), vi in yi.items():
            for i in c1.images_set.intersection(c2.images_set):
                model.addConstr(vi <= r[c1][i] + r[c2][i])

        for (c1, c2), vr in yr.items():
            for i in c2.images_set - c1.images_set:
                model.addConstr(vr <= r[c2][i])

        for c, imgs in q.items():
            for i, v in imgs.items():
                model.addConstr(q[c][i] <= p[c])
                if i in r[c]:
                    model.addConstr(q[c][i] <= 1 - r[c][i])

        model.setObjective(sum(obj), GRB.MAXIMIZE)
        model.optimize()

        for c, v in p.items():
            if v.x < 0.5:
                continue

            # Figure out what images are left in the clique
            rem_imgs = set(c.images)
            for i, riv in r[c].items():
                if riv.x > 0.5:
                    rem_imgs.remove(i)

            if len(rem_imgs) > 1:
                cliques.append(Clique(self.problem, rem_imgs, c.commands))

        return cliques
