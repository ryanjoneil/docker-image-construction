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
            for clique in self._subproblems():
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
                if c1.images_set - c2.images_set and c2.images_set - c1.images_set \
                   and (c1, c2) not in clique_inter_constraints:
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

    def _subproblems(self):
        return filter(None, [self._subproblem1()] + self._subproblem2())

    def _subproblem1(self):
        model = Model()
        model.params.OutputFlag = False
        model.params.LazyConstraints = True
        obj = []

        imgs = {}
        for i in self.problem.images:
            imgs[i] = v = model.addVar(name='i_%s' % i, vtype=GRB.BINARY)

        cmds = {}
        for c, t in self.problem.commands.items():
            cmds[c] = v = model.addVar(name='c_%s' % c, vtype=GRB.BINARY)
            obj.append(-t * v)

        y = {}
        for i, c in product(self.problem.images, self.problem.commands):
            y[i, c] = v = model.addVar(name='y_%s_%s' % (i, c), vtype=GRB.BINARY)
            obj.append(self.img_cmd_duals[i, c] * v)

        model.update()

        for i, c in product(self.problem.images, self.problem.commands):
            if c in self.problem.images[i]:
                model.addConstr(y[i, c] <= imgs[i])
                model.addConstr(y[i, c] <= cmds[c])
                model.addConstr(y[i, c] >= imgs[i] + cmds[c] - 1)
            else:
                model.addConstr(y[i, c] <= 0)
                model.addConstr(imgs[i] + cmds[c] <= 1)

        model.addConstr(quicksum(imgs.values()) >= 2)
        model.addConstr(quicksum(cmds.values()) == 1)

        model.setObjective(quicksum(obj), GRB.MAXIMIZE)

        def callback(m, where):
            if where != GRB.Callback.MIPSOL:
                return

        # TODO: add a d[None] for the line below
        # TODO: callback to cut off known cliques if a given d is on

        model.optimize()

        # print 'NEW:', model.objVal
        if model.status == GRB.OPTIMAL and model.objVal > 0:
            images = [i for i, v in imgs.items() if v.x > 0.5]
            commands = [c for c, v in cmds.items() if v.x > 0.5]

            # print 'NEW:', model.objVal, images, commands, parent

            return Clique(self.problem, images, commands)

        return None

    def _subproblem2(self):
        cliques = []
        for (c1, c2), pi in self.clique_inter_duals.items():
            if pi >= 0 or (len(c1.images) <= 2 and len(c2.images) <= 2):
                continue

            # TODO: this is a model where:
            # - each pair is either in its clique or alone
            # - the clique intersection is broken

            imgs_left_1 = c1.images_set
            imgs_left_2 = c1.images_set - c2.images_set
            imgs_right_1 = c2.images_set
            imgs_right_2 = c2.images_set - c1.images_set

            for imgs_left, imgs_right in [
                (imgs_left_1, imgs_right_1),
                (imgs_left_2, imgs_right_2)
            ]:
                cost_left = sum(self.problem.commands[c] for c in c1.commands)
                save_left = sum(self.img_cmd_duals[i, c] for i, c in product(imgs_left, c1.commands))

                cost_right = sum(self.problem.commands[c] for c in c2.commands)
                save_right = sum(self.img_cmd_duals[i, c] for i, c in product(imgs_right, c2.commands))

                if cost_left + cost_right - save_left - save_right + pi < 0:
                    if len(imgs_left) > 1:
                        cliques.append(Clique(self.problem, imgs_left, c1.commands))
                    if len(imgs_right) > 1:
                        cliques.append(Clique(self.problem, imgs_right, c2.commands))

        return cliques
