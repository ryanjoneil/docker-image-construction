from operator import itemgetter


class Solution(object):
    def __init__(self, problem, schedule, elapsed_time):
        self.problem = problem
        self.schedule = schedule
        self.elapsed_time = elapsed_time  # time to find the solution

    def stats(self):
        '''Returns (# of unique images, total compute time) of schedule'''
        seen = set()
        time = 0
        for sched in self.schedule.values():
            for i in range(len(sched)):
                commands = tuple(sched[:i+1])
                if commands not in seen:
                    seen.add(commands)
                    time += self.problem.commands[sched[i]]

        return len(seen), time

    def save(self, path):
        '''Saves a DICP solution to a json file'''
        # json formatting doen't make it very human readable, so we do our own.
        unique, time = self.stats()

        with open(path, 'w') as fp:
            fp.write('{\n')
            fp.write('    "elapsed_time": %f,\n' % self.elapsed_time.total_seconds())
            fp.write('    "unique_images": %d,\n' % unique)
            fp.write('    "compute_time": %d,\n' % time)
            fp.write('    "schedule": {\n')
            for j, (i, v) in enumerate(sorted(self.schedule.items(), key=itemgetter(0))):
                if j == len(self.schedule)-1:
                    end = '\n'
                else:
                    end = ',\n'
                fp.write(('        "%s": %r%s' % (i, v, end)).replace("'", '"').replace('u', ''))
            fp.write('    }\n')
            fp.write('}\n')
