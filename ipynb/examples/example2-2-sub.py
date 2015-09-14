from mosek.fusion import Model, Domain, Expr, ObjectiveSense
import sys

# Example 2. Column generation approach.
# Iteration 2, subproblem.
# Output:
#
#    Images:
#        w_1 = 1
#        w_2 = 1
#        w_3 = 1
#
#    Commands:
#        y_a = 0
#        y_b = 1
#        y_c = 0
#        y_d = 0
#
#    Interactions:
#        m_2 = 0
#        m_3 = 0
#        n_b = 1
#        n_c = 0
#        n_d = 0

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

# Variables to take images or commands from another clique.
m_2 = m.variable('m_2', *binary)
m_3 = m.variable('m_3', *binary)

n_b = m.variable('n_b', *binary)
n_c = m.variable('n_c', *binary)
n_d = m.variable('n_d', *binary)

# If something is taken out of a clique, it must either be put in the new
# clique or incur its own cost.
q_2_b = m.variable('q_2_b', *binary)
q_2_c = m.variable('q_2_c', *binary)
q_2_d = m.variable('q_2_d', *binary)

q_3_b = m.variable('q_3_b', *binary)
q_3_c = m.variable('q_3_c', *binary)
q_3_d = m.variable('q_3_d', *binary)

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

# Taking something from an existing clique means we must incur it cost.
m.constraint('d_2_b', Expr.sub(z_2_b, Expr.add([m_2, n_b])), Domain.lessThan(0.0))
m.constraint('d_2_c', Expr.sub(z_2_c, Expr.add([m_2, n_c])), Domain.lessThan(0.0))
m.constraint('d_2_d', Expr.sub(z_2_d, Expr.add([m_2, n_d])), Domain.lessThan(0.0))

m.constraint('d_2_b_q_2_b', Expr.sub(Expr.add([z_2_b, q_2_b]), Expr.add([m_2, n_b])), Domain.greaterThan(0.0))
m.constraint('d_2_c_q_2_c', Expr.sub(Expr.add([z_2_c, q_2_c]), Expr.add([m_2, n_c])), Domain.greaterThan(0.0))
m.constraint('d_2_d_q_2_d', Expr.sub(Expr.add([z_2_d, q_2_d]), Expr.add([m_2, n_d])), Domain.greaterThan(0.0))

m.constraint('d_3_b', Expr.sub(z_3_b, Expr.add([m_3, n_b])), Domain.lessThan(0.0))
m.constraint('d_3_c', Expr.sub(z_3_c, Expr.add([m_3, n_c])), Domain.lessThan(0.0))
m.constraint('d_3_d', Expr.sub(z_3_d, Expr.add([m_3, n_d])), Domain.lessThan(0.0))

m.constraint('d_3_b_q_3_b', Expr.sub(Expr.add([z_3_b, q_3_b]), Expr.add([m_3, n_b])), Domain.greaterThan(0.0))
m.constraint('d_3_c_q_3_c', Expr.sub(Expr.add([z_3_c, q_3_c]), Expr.add([m_3, n_c])), Domain.greaterThan(0.0))
m.constraint('d_3_d_q_3_d', Expr.sub(Expr.add([z_3_d, q_3_d]), Expr.add([m_3, n_d])), Domain.greaterThan(0.0))

# Maximize the amount we can improve our objective by adding a new clique.
obj1 = [Expr.mul(c, y) for c, y in [
    (r['A'], y_a), (r['B'], y_b), (r['C'], y_c), (r['D'], y_d)
]]
obj2 = [Expr.mul(c, z) for c, z in [
    # Individual image/command pairs
    (r['A'], z_1_a), (r['B'], z_1_b),
    (r['A'], z_2_a),
]]
obj3 = [Expr.mul(c, z) for c, z in [
    # Individual image/command pairs for commands that are now run alone
    (r['B'], q_2_b), (r['C'], q_2_c), (r['D'], q_2_d),
    (r['B'], q_3_b), (r['C'], q_3_c), (r['D'], q_3_d),
]]
obj4 = [Expr.mul(c, y) for c, y in [
    # Commands taken out of the existing cliques
    (r['B'], n_b), (r['C'], n_c), (r['D'], n_d)
]]


m.objective('w', ObjectiveSense.Maximize,
    Expr.sub(Expr.add(obj2 + obj4), Expr.add(obj1 + obj3))
)
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

print 'Interactions:'
print '\tm_2 = %.0f' % m_2.level()[0]
print '\tm_3 = %.0f' % m_3.level()[0]
print '\tn_b = %.0f' % n_b.level()[0]
print '\tn_c = %.0f' % n_c.level()[0]
print '\tn_d = %.0f' % n_d.level()[0]
print
