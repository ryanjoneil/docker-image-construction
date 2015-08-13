from .most_common import MostCommonHeuristic
from .most_time import MostTimeHeuristic
from collections import defaultdict
from itertools import product
from gurobipy import GRB, Model, quicksum as sum

class BIPModelGurobi(object):
    '''Reference binary integer program: full model with no decomposition'''
    _slug = 'bip-model-gurobi'

    def __init__(self, presol=None, heur=None, time=None):
        self.presol = presol
        self.heur = heur
        self.time = time # in minutes

    def slug(self):
        slug = BIPModelGurobi._slug
        if self.presol is not None:
            slug = '%s-presol-%s' % (slug, self.presol)
        if self.heur is not None:
            slug = '%s-heur-%s' % (slug, self.heur)
        return slug

    def solve(self, problem, saver):
        # Construct model.
        self.problem = problem
        self.model = model = Model()
        if self.time is not None:
            model.params.TimeLimit = 60 * int(self.time)

        # x[i,s,c] = 1 if image i runs command c during stage s, 0 otherwise.
        self.x = x = {}
        for i, cmds in problem.images.items():
            for s, c in product(problem.stages[i], cmds):
                x[i,s,c] = model.addVar(vtype=GRB.BINARY, name='x[%s,%s,%s]' % (i,s,c))

        # y[ip,iq,s,c] = 1 if images ip & iq have a shared path through stage
        #                s by running command c during s, 0 otherwise.
        y = {}
        for (ip, iq), cmds in problem.shared_cmds.items():
            for s, c in product(problem.shared_stages[ip, iq], cmds):
                y[ip,iq,s,c] = model.addVar(vtype=GRB.BINARY, name='y[%s,%s,%s,%s]' % (ip,iq,s,c))

        model.update()

        # TODO: need to remove presolved commands so the heuristic doesn't try them.

        # Add a heuristic initial solution.
        if self.heur is not None:
            self._heur()

        # Presolving
        if self.presol in ('all', 'unshared'):
            self._presol_unshared()
        if self.presol in ('all', 'shared'):
            self._presol_shared()

        # Each image one command per stage, and each command once.
        for i in problem.images:
            for s in problem.stages[i]:
                model.addConstr(sum(x[i,s,c] for c in problem.images[i]) == 1)
            for c in problem.images[i]:
                model.addConstr(sum(x[i,s,c] for s in problem.stages[i]) == 1)

        # Find shared paths among image pairs.
        for (ip, iq), cmds in problem.shared_cmds.items():
            for s in problem.shared_stages[ip,iq]:
                for c in cmds:
                    model.addConstr(y[ip,iq,s,c] <= x[ip,s,c])
                    model.addConstr(y[ip,iq,s,c] <= x[iq,s,c])
                if s > 1:
                    model.addConstr(sum(y[ip,iq,s,c] for c in cmds) <= sum(y[ip,iq,s-1,c] for c in cmds))

        model.setObjective(
            sum(problem.commands[c] * y[ip,iq,s,c] for ip,iq,s,c in y),
            GRB.MAXIMIZE
        )
        model.optimize(lambda *args: self._callback(saver, *args))

        # Create optimal schedule.
        schedule = defaultdict(list)
        for i, stages in problem.stages.items():
            for s in stages:
                for c in problem.images[i]:
                    if x[i,s,c].x > 0.5:
                        schedule[i].append(c)
                        break

        saver(schedule)

    def _callback(self, saver, model, where):
        # Save incumbent solutions as they are found.
        if where != GRB.callback.MIPSOL:
            return

        schedule = defaultdict(list)
        for i, stages in self.problem.stages.items():
            for s in stages:
                for c in self.problem.images[i]:
                    if model.cbGetSolution(self.x[i,s,c]) > 0.5:
                        schedule[i].append(c)
                        break

        saver(schedule)

    def _heur(self):
        # Find the heuristic we're supported to use.
        heur = None
        for h in (MostCommonHeuristic, MostTimeHeuristic):
            if self.heur == h._slug:
                heur = h()

        # Use heuristic for initial feasible solution.
        soln = []
        def save_initial(schedule):
            soln.append(schedule)
        heur.solve(self.problem, save_initial)
        init = soln.pop()

        # Inform the BIP model of this solution.
        for i,s,c in self.x:
            if init[i][s-1] == c:
                self.x[i,s,c].start = 1

    def _presol_unshared(self):
        # Find every command that no other image has. Fix them at the end.
        for img, cmds in self.problem.images.items():
            cmds = set(cmds)

            for img2, cmds2 in self.problem.images.items():
                if img2 == img:
                    continue
                cmds = cmds - set(cmds2)

                if not cmds:
                    break

            for s, c in zip(reversed(self.problem.stages[img]), cmds):
                print 'presol: x[%s,%s,%s] = 1' % (img,s,c)
                self.x[img,s,c].lb = 1

    def _presol_shared(self):
        pass
