This project assumes that you have already configured bugzoo to some extent. 

It requires that bugzoo be installed, that ManyBugs and GenProg be configured as sources in bugzoo, and that a bugzoo server is running.

On my machine, this can all be accomplished by invoking:

`pip3 install bugzoo`

`bugzoo source add manybugs https://github.com/squaresLab/ManyBugs`

`bugzoo source add genprog https://github.com/squaresLab/genprog-code`

`bugzoo tool build genprog`

`bugzood -p 6060`
