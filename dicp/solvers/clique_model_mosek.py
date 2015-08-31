from collections import defaultdict
from itertools import product
from mosek.fusion import Model, Domain, Expr, ObjectiveSense, AccSolutionStatus
import sys

class CliqueModelMosek(object):
    '''Transformed set packing model over maximal cliques'''
    _slug = 'clique-model-mosek'

    def __init__(self, presol=None, heur=None, time=None):
        self.time = time # in minutes

    def slug(self):
        return CliqueModelMosek._slug

    def solve(self, problem, saver):
        # Construct model.
        self.problem = problem

        # Do recursive maximal clique detection.
        self.clique_data = clique_data = problem.cliques()
        self.model = model = Model()
        if self.time is not None:
            model.setSolverParam('mioMaxTime', 60.0  * int(self.time))

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
                x[name] = v = self.model.variable(
                    name,
                    Domain.inRange(0.0, 1.0),
                    Domain.isInteger()
                )
                self._obj.append(Expr.mul(float(problem.commands[cmd]), v))
                by_img_cmd[img,cmd].append(v)

        # cliques[i] = 1 if clique i is used, 0 otherwise
        self.cliques = {}
        self._inter = 1
        self._update(clique_data)

        # Each image has to run each of its commands.
        for img_cmd, vlist in by_img_cmd.items():
            name = 'img-cmd-%s-%s' % img_cmd
            self.model.constraint(
                name,
                Expr.add(vlist),
                Domain.equalsTo(1.0)
            )

        model.objective('z', ObjectiveSense.Minimize, Expr.add(self._obj))
        model.setLogHandler(sys.stdout)
        model.acceptedSolutionStatus(AccSolutionStatus.Feasible)
        model.solve()

        # Translate the output of this to a schedule.
        schedule = defaultdict(list)
        self._translate(schedule, clique_data)
        for name, v in x.items():
            img, cmd = name.replace('x[','').replace(']','').split(',')
            if v.level()[0] > 0.5:
                schedule[img].append(cmd)
        saver(schedule)


    def _update(self, clique_data, parent=None):
        for c in clique_data['cliques']:
            self.cliques[c['name']] = v = self.model.variable(
                c['name'],
                Domain.inRange(0.0, 1.0),
                Domain.isInteger()
            )

            for img, cmd in product(c['images'], c['commands']):
                self.by_img_cmd[img,cmd].append(v)

            self._obj.append(Expr.mul(float(c['time']), v))

            if parent is not None:
                self.model.constraint(
                    'c-%s-%s' % (c['name'], parent['name']),
                    Expr.sub(v, self.cliques[parent['name']]),
                    Domain.lessThan(0.0)
                )

            for child in c['children']:
                self._update(child, c)

        for inter in clique_data['intersections']:
            self.model.constraint(
                'iter-%d' % self._inter,
                Expr.add([self.cliques[i] for i in inter]),
                Domain.lessThan(1.0)
            )
            self._inter += 1

    def _translate(self, schedule, data):
        for c in data['cliques']:
            if self.cliques[c['name']].level()[0] > 0.5:
                for img, cmd in product(c['images'], c['commands']):
                    schedule[img].append(cmd)
                for child in c['children']:
                   self._translate(schedule, child)

