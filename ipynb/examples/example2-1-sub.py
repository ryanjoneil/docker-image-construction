from mosek.fusion import Model, Domain, Expr, ObjectiveSense
import sys

# Example 2. Column generation approach.
# Iteration 1, subproblem.
# Output:
#
#    Images:
#        w_1 = 0
#        w_2 = 1
#        w_3 = 1
#
#    Commands:
#        y_a = 0
#        y_b = 1
#        y_c = 1
#        y_d = 1


r = {'A': 5.0, 'B': 10.0, 'C': 7.0, 'D': 12.0}

m = Model()
binary = (Domain.inRange(0.0, 1.0), Domain.isInteger())

# Variables to determine if we include commands in the clique.
y_a = m.variable('y_a', *binary)
y_b = m.variable('y_b', *binary)
y_c = m.variable('y_c', *binary)
y_d = m.variable('y_d', *binary)

# Variables to determine if we include images in the clique.
w_1 = m.variable('w_1', *binary)
w_2 = m.variable('w_2', *binary)
w_3 = m.variable('w_3', *binary)

# Variables to enforce relationships between y and w decisions.
z_1_a = m.variable('z_1_a', *binary)
z_1_b = m.variable('z_1_b', *binary)

z_2_a = m.variable('z_2_a', *binary)
z_2_b = m.variable('z_2_b', *binary)
z_2_c = m.variable('z_2_c', *binary)
z_2_d = m.variable('z_2_d', *binary)

z_3_b = m.variable('z_3_b', *binary)
z_3_c = m.variable('z_3_c', *binary)
z_3_d = m.variable('z_3_d', *binary)

# Inclusion of an image and a command means that image must
# use all command invocation from the clique.
# For instance:
#     (1) z_1_a <= w_1
#     (2) z_1_a <= y_a
#     (3) z_1_a >= w_1 + y_a - 1
m.constraint('c_1_a_1', Expr.sub(z_1_a, w_1), Domain.lessThan(0.0))
m.constraint('c_1_a_2', Expr.sub(z_1_a, y_a), Domain.lessThan(0.0))
m.constraint('c_1_a_3', Expr.sub(z_1_a, Expr.add([w_1, y_a])), Domain.greaterThan(-1.0))

m.constraint('c_1_b_1', Expr.sub(z_1_b, w_1), Domain.lessThan(0.0))
m.constraint('c_1_b_2', Expr.sub(z_1_b, y_b), Domain.lessThan(0.0))
m.constraint('c_1_b_3', Expr.sub(z_1_b, Expr.add([w_1, y_b])), Domain.greaterThan(-1.0))

m.constraint('c_1_c', Expr.sub(0.0, Expr.add([w_1, y_c])), Domain.greaterThan(-1.0))
m.constraint('c_1_d', Expr.sub(0.0, Expr.add([w_1, y_d])), Domain.greaterThan(-1.0))

m.constraint('c_2_a_1', Expr.sub(z_2_a, w_2), Domain.lessThan(0.0))
m.constraint('c_2_a_2', Expr.sub(z_2_a, y_a), Domain.lessThan(0.0))
m.constraint('c_2_a_3', Expr.sub(z_2_a, Expr.add([w_2, y_a])), Domain.greaterThan(-1.0))

m.constraint('c_2_b_1', Expr.sub(z_2_b, w_2), Domain.lessThan(0.0))
m.constraint('c_2_b_2', Expr.sub(z_2_b, y_b), Domain.lessThan(0.0))
m.constraint('c_2_b_3', Expr.sub(z_2_b, Expr.add([w_2, y_b])), Domain.greaterThan(-1.0))

m.constraint('c_2_c_1', Expr.sub(z_2_c, w_2), Domain.lessThan(0.0))
m.constraint('c_2_c_2', Expr.sub(z_2_c, y_c), Domain.lessThan(0.0))
m.constraint('c_2_c_3', Expr.sub(z_2_c, Expr.add([w_2, y_c])), Domain.greaterThan(-1.0))

m.constraint('c_2_d_1', Expr.sub(z_2_d, w_2), Domain.lessThan(0.0))
m.constraint('c_2_d_2', Expr.sub(z_2_d, y_d), Domain.lessThan(0.0))
m.constraint('c_2_d_3', Expr.sub(z_2_d, Expr.add([w_2, y_d])), Domain.greaterThan(-1.0))

m.constraint('c_3_a', Expr.sub(0.0, Expr.add([w_3, y_a])), Domain.greaterThan(-1.0))

m.constraint('c_3_b_1', Expr.sub(z_3_b, w_3), Domain.lessThan(0.0))
m.constraint('c_3_b_2', Expr.sub(z_3_b, y_b), Domain.lessThan(0.0))
m.constraint('c_3_b_3', Expr.sub(z_3_b, Expr.add([w_3, y_b])), Domain.greaterThan(-1.0))

m.constraint('c_3_c_1', Expr.sub(z_3_c, w_3), Domain.lessThan(0.0))
m.constraint('c_3_c_2', Expr.sub(z_3_c, y_c), Domain.lessThan(0.0))
m.constraint('c_3_c_3', Expr.sub(z_3_c, Expr.add([w_3, y_c])), Domain.greaterThan(-1.0))

m.constraint('c_3_d_1', Expr.sub(z_3_d, w_3), Domain.lessThan(0.0))
m.constraint('c_3_d_2', Expr.sub(z_3_d, y_d), Domain.lessThan(0.0))
m.constraint('c_3_d_3', Expr.sub(z_3_d, Expr.add([w_3, y_d])), Domain.greaterThan(-1.0))

# Maximize the amount we can improve our objective by adding a new clique.
obj1 = [Expr.mul(c, y) for c, y in [
    (r['A'], y_a), (r['B'], y_b), (r['C'], y_c), (r['D'], y_d)
]]
obj2 = [Expr.mul(c, z) for c, z in [
    # Individual image/command pairs
    (r['A'], z_1_a), (r['B'], z_1_b),
    (r['A'], z_2_a), (r['B'], z_2_b), (r['C'], z_2_c), (r['D'], z_2_d),
    (r['B'], z_3_b), (r['C'], z_3_c), (r['D'], z_3_d),
]]

m.objective('w', ObjectiveSense.Maximize, Expr.sub(Expr.add(obj2), Expr.add(obj1)))
m.setLogHandler(sys.stdout)
m.solve()

print
print 'Images:'
print '\tw_1 = %.0f' % w_1.level()[0]
print '\tw_2 = %.0f' % w_2.level()[0]
print '\tw_3 = %.0f' % w_3.level()[0]
print

print 'Commands:'
print '\ty_a = %.0f' % y_a.level()[0]
print '\ty_b = %.0f' % y_b.level()[0]
print '\ty_c = %.0f' % y_c.level()[0]
print '\ty_d = %.0f' % y_d.level()[0]
print

# print 'Image 3:'
# print '\tx_3_b = %.0f' % x_3_b.level()[0]
# print '\tx_3_c = %.0f' % x_3_c.level()[0]
# print '\tx_3_d = %.0f' % x_3_d.level()[0]
# print
