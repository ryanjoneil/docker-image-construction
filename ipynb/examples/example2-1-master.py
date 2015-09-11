from mosek.fusion import Model, Domain, Expr, ObjectiveSense
import sys

# Example 2. Column generation approach.
# Iteration 1, master problem.
# Output:
#
#    Image 1:
#        x_1_a = 1
#        x_1_b = 1
#
#    Image 2:
#        x_2_a = 1
#        x_2_b = 1
#        x_2_c = 1
#        x_2_d = 1
#
#    Image 3:
#        x_3_b = 1
#        x_3_c = 1
#        x_3_d = 1

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

# Each command must be run once for each image.
m.constraint('c_1_a', Expr.add([x_1_a]), Domain.equalsTo(1.0))
m.constraint('c_1_b', Expr.add([x_1_b]), Domain.equalsTo(1.0))
m.constraint('c_2_a', Expr.add([x_2_a]), Domain.equalsTo(1.0))
m.constraint('c_2_b', Expr.add([x_2_b]), Domain.equalsTo(1.0))
m.constraint('c_2_c', Expr.add([x_2_c]), Domain.equalsTo(1.0))
m.constraint('c_2_d', Expr.add([x_2_d]), Domain.equalsTo(1.0))
m.constraint('c_3_b', Expr.add([x_3_b]), Domain.equalsTo(1.0))
m.constraint('c_3_c', Expr.add([x_3_c]), Domain.equalsTo(1.0))
m.constraint('c_3_d', Expr.add([x_3_d]), Domain.equalsTo(1.0))

# Minimize resources required to construct all images.
obj = [Expr.mul(c, x) for c, x in [
    # Individual image/command pairs
    (r['A'], x_1_a), (r['B'], x_1_b),
    (r['A'], x_2_a), (r['B'], x_2_b), (r['C'], x_2_c), (r['D'], x_2_d),
    (r['B'], x_3_b), (r['C'], x_3_c), (r['D'], x_3_d),

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
