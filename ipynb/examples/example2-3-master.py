from mosek.fusion import Model, Domain, Expr, ObjectiveSense
import sys

# Example 2. Column generation approach.
# Iteration 3, master problem.
# Output:
#
#    Image 1:
#        x_1_a = 1
#        x_1_b = 1
#
#    Image 2:
#        x_2_a = 1
#        x_2_b = 0
#        x_2_c = 0
#        x_2_d = 0
#
#    Image 3:
#        x_3_b = 0
#        x_3_c = 0
#        x_3_d = 0
#
#    Cliques:
#        x_23_bcd = 1

r = {'A': 5.0, 'B': 10.0, 'C': 7.0, 'D': 12.0}

m = Model()
binary = (Domain.inRange(0.0, 1.0), Domain.isInteger())

# Provide a variable for each image and command. This is 1 if the command
# is not run as part of a clique for the image.
x_1_a = m.variable('x_1_a', *binary)
x_1_b = m.variable('x_1_b', *binary)

x_2_a = m.variable('x_2_a', *binary)
x_2_b = m.variable('x_2_b', *binary)
x_2_c = m.variable('x_2_c', *binary)
x_2_d = m.variable('x_2_d', *binary)

x_3_b = m.variable('x_3_b', *binary)
x_3_c = m.variable('x_3_c', *binary)
x_3_d = m.variable('x_3_d', *binary)

# Provide a variable for each maximal clique and maximal sub-clique.
x_23_bcd = m.variable('x_23_bcd', *binary)

x_123_b = m.variable('x_123_b', *binary)
x_123_b_23_cd = m.variable('x_123_b_23_cd', *binary)

# Each command must be run once for each image.
m.constraint('c_1_a', Expr.add([x_1_a]), Domain.equalsTo(1.0))
m.constraint('c_1_b', Expr.add([x_1_b, x_123_b]), Domain.equalsTo(1.0))
m.constraint('c_2_a', Expr.add([x_2_a]), Domain.equalsTo(1.0))
m.constraint('c_2_b', Expr.add([x_2_b, x_23_bcd, x_123_b]), Domain.equalsTo(1.0))
m.constraint('c_2_c', Expr.add([x_2_c, x_23_bcd, x_123_b_23_cd]), Domain.equalsTo(1.0))
m.constraint('c_2_d', Expr.add([x_2_d, x_23_bcd, x_123_b_23_cd]), Domain.equalsTo(1.0))
m.constraint('c_3_b', Expr.add([x_3_b, x_23_bcd, x_123_b]), Domain.equalsTo(1.0))
m.constraint('c_3_c', Expr.add([x_3_c, x_23_bcd, x_123_b_23_cd]), Domain.equalsTo(1.0))
m.constraint('c_3_d', Expr.add([x_3_d, x_23_bcd, x_123_b_23_cd]), Domain.equalsTo(1.0))

# Add dependency constraints for sub-cliques.
m.constraint('d_123_b_23_cd', Expr.sub(x_123_b, x_123_b_23_cd), Domain.greaterThan(0.0))

# Eliminated intersections between cliques.
m.constraint('e1', Expr.add([x_23_bcd, x_123_b]), Domain.lessThan(1.0))

# Minimize resources required to construct all images.
obj = [Expr.mul(c, x) for c, x in [
    # Individual image/command pairs
    (r['A'], x_1_a), (r['B'], x_1_b),
    (r['A'], x_2_a), (r['B'], x_2_b), (r['C'], x_2_c), (r['D'], x_2_d),
    (r['B'], x_3_b), (r['C'], x_3_c), (r['D'], x_3_d),

    # Cliques
    (r['B'] + r['C'] + r['D'], x_23_bcd),
    (r['B'], x_123_b),
    (r['C'] + r['D'], x_123_b_23_cd),
]]
m.objective('w', ObjectiveSense.Minimize, Expr.add(obj))
m.setLogHandler(sys.stdout)
m.solve()

print
print 'Image 1:'
print '\tx_1_a = %.0f' % x_1_a.level()[0]
print '\tx_1_b = %.0f' % x_1_b.level()[0]
print

print 'Image 2:'
print '\tx_2_a = %.0f' % x_2_a.level()[0]
print '\tx_2_b = %.0f' % x_2_b.level()[0]
print '\tx_2_c = %.0f' % x_2_c.level()[0]
print '\tx_2_d = %.0f' % x_2_d.level()[0]
print

print 'Image 3:'
print '\tx_3_b = %.0f' % x_3_b.level()[0]
print '\tx_3_c = %.0f' % x_3_c.level()[0]
print '\tx_3_d = %.0f' % x_3_d.level()[0]
print

print 'Cliques:'
print '\tx_23_bcd = %.0f' % x_23_bcd.level()[0]
print '\tx_123_b = %.0f' % x_123_b.level()[0]
print '\tx_123_b_23_cd = %.0f' % x_123_b_23_cd.level()[0]
print
