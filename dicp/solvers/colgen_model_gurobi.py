from collections import defaultdict
from dicp.clique import Clique
from gurobipy import GRB, Model, quicksum as sum
from itertools import product
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

        # Starting cliques and their parents
        self.cliques = defaultdict(lambda: None)  # clique -> parent clique
        self.parent_img_cliques = defaultdict(lambda: set())  # (parent, img) -> [cliques]

        self.img_cmd_to_cliques = defaultdict(list)
        for img, cmds in problem.images.items():
            for cmd in cmds:
                clique = Clique(problem, [img], [cmd])
                self.cliques[clique] = clique.parent
                self.img_cmd_to_cliques[img, cmd].append(clique)

        for iteration in range(1000):
            print '[iteration %02d / %s]' % (iteration + 1, time.asctime())

            done = True
            self._master()
            clique = self._subproblem()
            if clique is not None and clique not in self.cliques:
                print '[new clique] %s' % clique

                done = False
                self.cliques[clique] = clique.parent
                for img, cmd in product(clique.images, clique.commands):
                    self.img_cmd_to_cliques[img, cmd].append(clique)
                for img in clique.images:
                    self.parent_img_cliques[img, clique.parent].add(clique)

            if done:
                solution = self._master(final=True)

                print '\n[solution]'
                for clique in solution:
                    if len(clique.images) > 1:
                        print clique

                print '\n[cliques]'
                for clique in self.cliques:
                    if len(clique.images) > 1:
                        print clique
                break
            print

    def _master(self, final=False):
        self.num_cmds_dual = 0.0
        self.img_cmd_duals = defaultdict(float)
        self.clique_inter_duals = defaultdict(float)
        self.clique_depend_duals = defaultdict(float)

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

        # Max number of (image, command) pairs
        num_cmds_by_clique = [clique.size * x[clique] for clique in self.cliques]
        num_cmds_constraint = model.addConstr(sum(num_cmds_by_clique) <= self.problem.num_pairs)

        # Each image has to run each of its commands.
        img_cmd_constraints = {}
        for img, cmds in self.problem.images.items():
            for cmd in cmds:
                vlist = [x[c] for c in self.img_cmd_to_cliques[img, cmd]]
                if final:
                    model.addConstr(sum(vlist) == 1)
                else:
                    img_cmd_constraints[img, cmd] = model.addConstr(sum(vlist) >= 1)

        # Cliques with the same parent and image can only have one on (ignores 1x1)
        clique_inter_constraints = {}
        for (parent, img), cliques in self.parent_img_cliques.items():
            if len(cliques) > 1:
                clique_inter_constraints[parent, img] = model.addConstr(sum(x[c] for c in cliques) <= 1)

        # Dependency relationships
        clique_depend_constraints = {}
        for clique in self.cliques:
            if clique.parent:
                clique_depend_constraints[clique.parent, clique] = model.addConstr(
                    x[clique] <= x[clique.parent]
                )

        model.setObjective(sum(obj), GRB.MINIMIZE)
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

            if num_cmds_constraint.pi:
                print '[cmds dual] = %.02f' % num_cmds_constraint.pi
            self.num_cmds_dual = num_cmds_constraint.pi

            for (parent, img), c in clique_inter_constraints.items():
                if c.pi:
                    print '[clique/inter dual] { %s & %s } = %.02f' % (parent, img, c.pi)
                self.clique_inter_duals[parent, img] = c.pi

            for clique, c in clique_depend_constraints.items():
                if c.pi:
                    print '[clique/depend dual] %s = %.02f' % (clique, c.pi)
                self.clique_depend_duals[clique] = c.pi

    def _subproblem(self):
        model = Model()
        model.params.OutputFlag = False
        model.params.LazyConstraints = True
        obj = []

        imgs = {}
        for i in self.problem.images:
            imgs[i] = v = model.addVar(name='i_%s' % i, vtype=GRB.BINARY)
            # TODO: not sure if this goes here...

        cmds = {}
        for c, t in self.problem.commands.items():
            cmds[c] = v = model.addVar(name='c_%s' % c, vtype=GRB.BINARY)
            obj.append(-t * v)

        y = {}
        for i, c in product(self.problem.images, self.problem.commands):
            y[i, c] = v = model.addVar(name='y_%s_%s' % (i, c), vtype=GRB.BINARY)
            obj.append(self.img_cmd_duals[i, c] * v)

        d = {None: model.addVar(name='d_none', vtype=GRB.BINARY)}
        for clique in self.cliques:
            if clique.size <= 1:
                continue
            d[clique] = v = model.addVar(name='d_%s' % (clique,), vtype=GRB.BINARY)

        for (p, _), pi in self.clique_depend_duals.items():
            obj.append(pi * d[p])

        # TODO: incorporate duals
        # obj.append()

        for (i, p), pi in self.clique_inter_duals.items():
            obj.append(pi * (d[p])) # + imgs[i]))
            # obj.append(pi * (d[p] + imgs[i]))

        model.update()

        for i, c in product(self.problem.images, self.problem.commands):
            if c in self.problem.images[i]:
                model.addConstr(y[i, c] <= imgs[i])
                model.addConstr(y[i, c] <= cmds[c])
                model.addConstr(y[i, c] >= imgs[i] + cmds[c] - 1)
            else:
                model.addConstr(y[i, c] <= 0)
                model.addConstr(imgs[i] + cmds[c] <= 1)

        model.addConstr(sum(imgs.values()) >= 2)
        model.addConstr(sum(cmds.values()) >= 1)
        model.addConstr(sum(d.values()) == 1)

        # We can depend on another clique, but that eliminates (img, cmd) pairs
        for clique, v in d.items():
            if clique is None:
                continue

            for i, cs in self.problem.images.items():
                if i in clique.remaining:
                    cs = set(cs)
                    for c in self.problem.images[i]:
                        if c not in cs:
                            model.addConstr(y[i, c] <= 1 - v)

                else:
                    model.addConstr(imgs[i] <= 1 - v)

            for c in self.problem.commands:
                if c not in clique.remaining_commands:
                    model.addConstr(cmds[c] <= 1 - v)

        model.setObjective(sum(obj) + self.num_cmds_dual, GRB.MAXIMIZE)

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

            parent = None
            for clique, v in d.items():
                if v.x > 0.5:
                    parent = clique
                    break

            # print 'NEW:', model.objVal, images, commands, parent

            # TODO: parent
            return Clique(self.problem, images, commands, parent=parent)

        return None
