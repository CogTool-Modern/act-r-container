#!/bin/bash
set -e
set -m

if [ "$1" = "/start-it.sh" ] || [ "$1" = "start-it.sh" ]; then
  shift
fi

prepare_tutorial_dir() {
  mkdir -p actr7.x/tutorial

  if [ -d actr7.x/original-tutorial ]; then
    cp -n -r -t actr7.x/tutorial actr7.x/original-tutorial/*
  fi
}

if [ "$1" = '' ]

then
 
  prepare_tutorial_dir
  
  sbcl --load "quicklisp/setup.lisp" --load "actr7.x/load-act-r.lisp" --eval '(progn (init-des) (echo-act-r-output) (mp-print-versions) (run-node-env))'

elif [ "$1" = "act-r.sh" ]
then
  
  prepare_tutorial_dir
  sed -i -e "s/which_interface = 1/which_interface = 4/" -e "s/start-normal -->/start-normal/" -e "s/<\!-- end-normal/end-normal/" -e "s/<\!-- start-container/<\!-- start-container -->/" -e "s/end-container -->/<\!-- end-container -->/" actr7.x/examples/connections/nodejs/environment.html
  sed -i -e "s/which_interface = 1/which_interface = 4/" actr7.x/examples/connections/nodejs/expwindow.html

  /act-r.sh

elif [ "$1" = "run-jupyter.sh" ]
then

  sed -i -e "s/which_interface = 1/which_interface = 3/" -e "s/start-normal -->/start-normal/" -e "s/<\!-- end-normal/end-normal/" -e "s/<\!-- start-container/<\!-- start-container -->/" -e "s/end-container -->/<\!-- end-container -->/" actr7.x/examples/connections/nodejs/environment.html
  sed -i -e "s/which_interface = 1/which_interface = 3/" actr7.x/examples/connections/nodejs/expwindow.html
 
  prepare_tutorial_dir

  export PYTHONPATH=${PYTHONPATH}:${HOME}/actr7.x/tutorial/python

  sbcl --non-interactive --load "quicklisp/setup.lisp" --load "actr7.x/load-act-r.lisp" --eval '(progn (init-des) (run-node-env) (loop))' > /dev/null 2>&1 &

  /run-jupyter.sh

elif [ "$1" = "heroku-web" ]
then

  prepare_tutorial_dir

  exec sbcl --non-interactive --load "quicklisp/setup.lisp" --load "actr7.x/load-act-r.lisp" --eval '(progn (init-des) (echo-act-r-output) (mp-print-versions) (run-node-env) (loop))'

else 

  sed -i -e "s/which_interface = 1/which_interface = 2/" -e "s/start-normal -->/start-normal/" -e "s/<\!-- end-normal/end-normal/" -e "s/<\!-- start-container/<\!-- start-container -->/" -e "s/end-container -->/<\!-- end-container -->/" actr7.x/examples/connections/nodejs/environment.html
  sed -i -e "s/which_interface = 1/which_interface = 2/" actr7.x/examples/connections/nodejs/expwindow.html
  
  prepare_tutorial_dir

  export PYTHONPATH=${PYTHONPATH}:${HOME}/actr7.x/tutorial/python
  
  sbcl --non-interactive --load "quicklisp/setup.lisp" --load "actr7.x/load-act-r.lisp" --eval '(progn (init-des) (run-node-env) (loop))' > /dev/null 2>&1 &
  
  exec "$@"

fi
