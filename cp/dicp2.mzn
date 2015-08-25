include "all_different.mzn";

int: nstages = 4;
int: ncommands = 4;

set of int: images = 1..3;
set of int: stages = 1..nstages;
set of int: commands = 1..ncommands;

% Amount of time a command takes
array[commands] of int: time = [105,10,10,20];

% Individual schedules
array[1..2] of var {1,2}: y1;
array[1..4] of var {1,2,3,4}: y2;
array[1..3] of var {2,3,4}: y3;

constraint all_different(y1);
constraint all_different(y2);
constraint all_different(y3);

% Arcs from 0 to first node
array[commands] of var bool: source;
constraint forall(c in commands)(
  source[c] >= (y1[1] == c \/ y2[1] == c \/ y3[1] == c)
);

% Arcs from one node to the next
array[1..(nstages-1),commands,commands] of var bool: arcs;
constraint forall(
  s in 1..(nstages-1), c1 in commands, c2 in commands where c1 != c2
)(
  (s > length(y1) \/ arcs[s,c1,c2] >= (y1[s] == c1 /\ y1[s+1] == c2)) /\
  (s > length(y2) \/ arcs[s,c1,c2] >= (y2[s] == c1 /\ y2[s+1] == c2)) /\
  (s > length(y3) \/ arcs[s,c1,c2] >= (y3[s] == c1 /\ y3[s+1] == c2))
);

% Number of routes going into each node
array[stages,commands] of var int: node_entries;
constraint forall(c in commands)(node_entries[1,c] = source[c]);
constraint forall(s in 2..nstages, c2 in commands)(
  node_entries[s,c2] = sum(c1 in commands where c1 != c2)(
    arcs[s-1,c1,c2] * node_entries[s-1,c1]
  )
);

% Total compute time required to construct the image
var int: total_time = sum(s in stages, c in commands)(time[c] * node_entries[s,c]);

solve minimize total_time;

output [
  "w = ", show(total_time), "\n",
  "y1 = ", show(y1), "\n",
  "y2 = ", show(y2), "\n",
  "y3 = ", show(y3), "\n"
];

