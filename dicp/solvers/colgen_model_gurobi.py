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

        for (c1, c2), pi in self.clique_inter_duals.items():
            int_images = c1.images_set.intersection(c2.images_set)

            # Remove images in c1 not in c2
            z = pi - c1.cost
            for i in int_images:
                dual = sum(self.img_cmd_duals[i, cmd] for cmd in c1.commands)
                z += dual

            if z > 0:
                cliques.append(Clique(self.problem, int_images, c1.commands))

            # Remove images in c2 not in c1
            z = pi - c2.cost
            for i in int_images:
                dual = sum(self.img_cmd_duals[i, cmd] for cmd in c2.commands)
                z += dual

            if z > 0:
                cliques.append(Clique(self.problem, int_images, c2.commands))

            # Pare images off until they don't intersect anymore
            if len(c1.images) <= 2 or len(c2.images) <= 2:
                continue

            model = Model()
            model.params.OutputFlag = False

            # model.params.OutputFlag = False
            obj = [pi]

            p1 = model.addVar(vtype=GRB.BINARY)
            p2 = model.addVar(vtype=GRB.BINARY)
            q1 = {i: model.addVar(vtype=GRB.BINARY) for i in c1.images}
            q2 = {i: model.addVar(vtype=GRB.BINARY) for i in c2.images}
            r1 = {i: model.addVar(vtype=GRB.BINARY) for i in int_images}
            r2 = {i: model.addVar(vtype=GRB.BINARY) for i in int_images}

            model.update()

            obj.append(-c1.cost * p1)
            obj.append(-c2.cost * p2)

            for i in c1.images:
                dual = sum(self.img_cmd_duals[i, cmd] for cmd in c1.commands)
                obj.append(dual * q1[i])

            for i in c2.images:
                dual = sum(self.img_cmd_duals[i, cmd] for cmd in c2.commands)
                obj.append(dual * q2[i])

            for i in int_images:
                model.addConstr(p1 <= r1[i] + r2[i])
                model.addConstr(p2 <= r1[i] + r2[i])

            for i in c1.images:
                model.addConstr(q1[i] <= p1)
                if i in int_images:
                    model.addConstr(q1[i] <= 1 - r1[i])

            for i in c2.images:
                model.addConstr(q2[i] <= p1)
                if i in int_images:
                    model.addConstr(q2[i] <= 1 - r2[i])

            model.setObjective(sum(obj), GRB.MAXIMIZE)
            model.optimize()

            for c, v, r in [(c1, p1, r1), (c2, p2, r2)]:
                if v.x < 0.5:
                    continue

                # Figure out what images are left in the clique
                rem_imgs = set(c.images)
                for i, riv in r.items():
                    if riv.x > 0.5:
                        rem_imgs.remove(i)

                if len(rem_imgs) > 1:
                    cliques.append(Clique(self.problem, rem_imgs, c.commands))
                rem_imgs_1 = set(c1.images)
                rem_imgs_2 = set(c2.images)

                z = -c1.cost - c2.cost
                for i in int_images:
                    dual1 = sum(self.img_cmd_duals[i, cmd] for cmd in c1.commands)
                    dual2 = sum(self.img_cmd_duals[i, cmd] for cmd in c2.commands)
                    if dual1 > dual2:
                        rem_imgs_1.remove(i)
                        z += dual1
                    else:
                        rem_imgs_2.remove(i)
                        z += dual2

                if z > 0:
                    cliques.append(Clique(self.problem, rem_imgs_1, c1.commands))
                    cliques.append(Clique(self.problem, rem_imgs_2, c2.commands))

        return cliques
