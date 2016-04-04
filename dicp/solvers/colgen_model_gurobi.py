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
            # One clique for all commands
            all_sig = ((img,), tuple(sorted(cmds)))
            self.cliques.add(all_sig)
            for cmd in cmds:
                self.img_cmd_to_cliques[img, cmd].append(all_sig)

            # And one clique per command
            if len(cmds) > 1:
                for cmd in cmds:
                    sig = ((img,), (cmd,))
                    self.cliques.add(sig)
                    self.img_cmd_to_cliques[img, cmd].append(sig)

        for iteration in range(100):
            print '[iteration %02d / %s]' % (iteration + 1, time.asctime())

            done = True
            self._master()

            for sig in self._subproblem():
                imgs, cmds = sig
                if imgs and cmds and sig not in self.cliques:
                    print '[new clique] {%s, %s}' % (' '.join(map(str, imgs)), ' '.join(map(str, cmds)))

                    done = False
                    self.cliques.add(sig)
                    for img, cmd in product(imgs, cmds):
                        self.img_cmd_to_cliques[img, cmd].append(sig)

            if done:
                for imgs, cmds in sorted(self._master(final=True)):
                    if len(imgs) > 1:
                        print '{%s, %s}' % (' '.join(map(str, imgs)), ' '.join(map(str, cmds)))

                print '\n[cliques]'
                for imgs, cmds in sorted(self.cliques):
                    if len(imgs) > 1:
                        print '{%s, %s}' % (' '.join(map(str, imgs)), ' '.join(map(str, cmds)))

                break

            print

    def _master(self, final=False):
        self.num_cmds_dual = 0.0
        self.img_cmd_duals = defaultdict(float)
        self.clique_bound_duals = defaultdict(float)
        self.clique_inter_duals = defaultdict(float)

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
        num_cmds_by_clique = [len(sig[0]) * len(sig[1]) * x[sig] for sig in self.cliques]
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

        # Upper bounds on cliques
        clique_bound_constraints = {}
        if not final:
            for sig in self.cliques:
                clique_bound_constraints[sig] = model.addConstr(x[sig] <= 1)

        # Cliques that intersect can only have one on
        clique_inter_constraints = {}
        for sig1, sig2 in combinations(self.cliques, 2):
            sig1, sig2 = tuple(sorted([sig1, sig2]))
            imgs1, cmds1 = sig1
            imgs2, cmds2 = sig2

            if imgs1 == imgs2 or not set(imgs1).intersection(set(imgs2)):
                continue

            if (len(imgs1) < 2 or len(imgs2) < 2) and not set(cmds1).intersection(cmds2):
                continue

            if (set(imgs1) < set(imgs2) or set(imgs2) < set(imgs1)):
                if not set(cmds1).intersection(set(cmds2)):
                    continue

            clique_inter_constraints[sig1, sig2] = model.addConstr(x[sig1] + x[sig2] <= 1)

        model.setObjective(sum(obj), GRB.MINIMIZE)
        model.optimize()

        if final:
            print '\n[obj: %.02f]' % model.objVal
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
                        self.img_cmd_duals[img, cmd] = img_cmd_constraints[img, cmd].pi
                        duals.append(round(img_cmd_constraints[img, cmd].pi, 1) or '')
                    except KeyError:
                        duals.append('')
                print '% 4s | %s' % (img, ' '.join('% 6s' % d for d in duals))
            print '-' * len(header)

            if num_cmds_constraint.pi:
                print '[cmds dual] = %.02f' % num_cmds_constraint.pi
            self.num_cmds_dual = num_cmds_constraint.pi

            for k, c in sorted(clique_bound_constraints.items()):
                imgs = ' '.join(map(str, k[0]))
                cmds = ' '.join(map(str, k[1]))
                if c.pi:
                    print '[clique/bound dual] {%s, %s} = %.02f' % (imgs, cmds, c.pi)
                self.clique_bound_duals[k] = c.pi

            for k, c in sorted(clique_inter_constraints.items()):
                imgs1 = ' '.join(map(str, k[0][0]))
                cmds1 = ' '.join(map(str, k[0][1]))
                imgs2 = ' '.join(map(str, k[1][0]))
                cmds2 = ' '.join(map(str, k[1][1]))
                if c.pi:
                    print '[clique/inter dual] {%s, %s} | {%s, %s} = %.02f' % (imgs1, cmds1, imgs2, cmds2, c.pi)
                self.clique_inter_duals[k] = c.pi

    def _subproblem(self):
        model = Model()
        model.setParam('OutputFlag', False)
        obj = []

        imgs = {}
        for i in self.problem.images:
            imgs[i] = v = model.addVar(name='i_%s' % i, vtype=GRB.BINARY)

        cmds = {}
        for c, t in self.problem.commands.items():
            cmds[c] = v = model.addVar(name='c_%s' % c, vtype=GRB.BINARY)
            obj.append(t * v)

        y = {}
        for i, c in product(self.problem.images, self.problem.commands):
            y[i, c] = v = model.addVar(name='y_%s_%s' % (i, c), vtype=GRB.BINARY)
            obj.append(-self.img_cmd_duals[i, c] * v)

        d = {}
        for (sig1, sig2), dual in self.clique_inter_duals.items():
            if dual < 0:
                d[sig1, sig2] = v = model.addVar(vtype=GRB.BINARY)

        model.update()

        for i, c in product(self.problem.images, self.problem.commands):
            if c in self.problem.images[i]:
                model.addConstr(y[i, c] <= imgs[i])
                model.addConstr(y[i, c] <= cmds[c])
                model.addConstr(y[i, c] >= imgs[i] + cmds[c] - 1)
            else:
                model.addConstr(y[i, c] <= imgs[i])
                model.addConstr(y[i, c] <= 0)
                model.addConstr(y[i, c] >= imgs[i] + cmds[c] - 1)

        for (sig1, sig2), v in d.items():
            imgs1, cmds1 = sig1
            imgs2, cmds2 = sig2

            inter_imgs = set(imgs1).intersection(set(imgs2))
            for i in inter_imgs:
                model.addConstr(v <= imgs[i])

            inter_cmds = set(cmds1).intersection(set(cmds2))
            for c in inter_cmds:
                model.addConstr(v <= cmds[c])

            cost = sum(self.problem.commands[c] * len(inter_imgs) for c in inter_cmds)
            obj.append((cost + self.clique_inter_duals[sig1, sig2]) * v)

        model.setObjective(sum(obj), GRB.MINIMIZE)
        model.optimize()

        if model.objVal < 0:
            images = tuple(sorted([i for i, v in imgs.items() if v.x > 0.5]))
            commands = tuple(sorted([c for c, v in cmds.items() if v.x > 0.5]))
            return [(images, commands)]

        return []
