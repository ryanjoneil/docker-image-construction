include "all_different.mzn";

array[1..4] of int: t = [105,10,10,20];

array[1..2] of var {1,2}: x1;
array[1..4] of var {1,2,3,4}: x2;
array[1..3] of var {2,3,4}: x3;

constraint all_different(x1);
constraint all_different(x2);
constraint all_different(x3);

array[1..2] of var bool: y12;
constraint y12[1] = (x1[1] == x2[1]);
constraint y12[2] = (y12[1] /\ x1[2] == x2[2]);

array[1..2] of var bool: y13;
constraint y13[1] = (x1[1] == x3[1]);
constraint y13[2] = (y13[1] /\ x1[2] == x3[2]);

array[1..3] of var bool: y23;
constraint y23[1] = (x2[1] == x3[1]);
constraint forall(i in 2..3)(y23[i] = (y23[i-1] /\ x2[i] == x3[i]));

var int: z = sum(i in 1..2)(t[x1[i]]*y12[i])
           + sum(i in 1..2)(t[x1[i]]*y13[i])
           + sum(i in 1..3)(t[x2[i]]*y23[i]);

solve maximize z;

output [
  "z = ", show(z), "\n",
  "x1 = ", show(x1), "\n",
  "x2 = ", show(x2), "\n",
  "x3 = ", show(x3) 
];