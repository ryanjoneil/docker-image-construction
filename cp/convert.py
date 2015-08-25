import json

foo = json.load(open('input.json'))

print 'include "all_different.mzn";'
print 'array[1..%d] of int: t = [%s];' % (len(foo['commands']), ','.join(str(foo['commands'][x]) for x in sorted(foo['commands'])))

for i, cmds in foo['images'].items():
    print 'array[1..%d] of var {%s}: x%d;' % (len(cmds), ','.join(c.lstrip('0') for c in cmds), int(i))
    print 'constraint all_different(x%d);' % int(i)

z = []
items = foo['images'].items()
for a, (i, cmds) in enumerate(items):
    for j, cmdsj in items[a+1:]:
        l = len(set(cmds).intersection(set(cmdsj)))
        if not l:
            continue
        z.append('sum(i in 1..%d)(t[x%d[i]]*y%d%d[i])' % (l, int(i), int(i), int(j)))
        print 'array[1..%d] of var bool: y%d%d;' % (l, int(i), int(j))
        print 'constraint y%d%d[1] = (x%d[1] == x%d[1]);' % (int(i), int(j), int(i), int(j))
        if l > 1:
            print 'constraint forall(i in 2..%d)(y%d%d[i] = (y%d%d[i-1] /\ x%d[i] == x%d[i]));' % (l, int(i), int(j), int(i), int(j), int(i), int(j))

print 'var int: z = %s;' % ' + '.join(z)
print 'solve maximize z;'

print 'output ['
print '  "z = ", show(z), "\\n",'
for i in foo['images']:
  print '  "x%d = ", show(x%d), "\\n",' % (int(i), int(i))
print '  "ok"'
print '];'
