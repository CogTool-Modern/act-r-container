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

elif [ "$1" = "heroku-api" ]
then

  prepare_tutorial_dir

  ACTR_REMOTE_INTERNAL_PORT="${ACTR_REMOTE_INTERNAL_PORT:-12650}"
  case "${ACTR_REMOTE_INTERNAL_PORT}" in
    ''|*[!0-9]*)
      echo "ACTR_REMOTE_INTERNAL_PORT must be numeric." >&2
      exit 1
      ;;
  esac

  if [ -n "${PORT:-}" ] && [ "${ACTR_REMOTE_INTERNAL_PORT}" = "${PORT}" ]; then
    if [ "${PORT}" = "12650" ]; then
      ACTR_REMOTE_INTERNAL_PORT=12651
    else
      ACTR_REMOTE_INTERNAL_PORT=12650
    fi
  fi

  python3 "${HOME}/actr_api_server.py" &
  API_PID="$!"
  API_PORT="${PORT:-8080}"

  for _ in $(seq 1 60); do
    if ! kill -0 "${API_PID}" 2>/dev/null; then
      wait "${API_PID}"
      exit "$?"
    fi
    if python3 -c "import socket; s=socket.create_connection(('127.0.0.1', int('${API_PORT}')), timeout=1); s.close()" 2>/dev/null; then
      break
    fi
    sleep 1
  done

  sbcl --non-interactive --eval '(pushnew :standalone *features*)' --load "quicklisp/setup.lisp" --load "actr7.x/load-act-r.lisp" --eval "(progn (start-des nil nil ${ACTR_REMOTE_INTERNAL_PORT}) (echo-act-r-output) (mp-print-versions) (loop))" &

  for _ in $(seq 1 60); do
    if [ -s "${HOME}/act-r-address.txt" ] && [ -s "${HOME}/act-r-port-num.txt" ]; then
      break
    fi
    sleep 1
  done

  wait "${API_PID}"

else 

  sed -i -e "s/which_interface = 1/which_interface = 2/" -e "s/start-normal -->/start-normal/" -e "s/<\!-- end-normal/end-normal/" -e "s/<\!-- start-container/<\!-- start-container -->/" -e "s/end-container -->/<\!-- end-container -->/" actr7.x/examples/connections/nodejs/environment.html
  sed -i -e "s/which_interface = 1/which_interface = 2/" actr7.x/examples/connections/nodejs/expwindow.html
  
  prepare_tutorial_dir

  export PYTHONPATH=${PYTHONPATH}:${HOME}/actr7.x/tutorial/python
  
  sbcl --non-interactive --load "quicklisp/setup.lisp" --load "actr7.x/load-act-r.lisp" --eval '(progn (init-des) (run-node-env) (loop))' > /dev/null 2>&1 &
  
  exec "$@"

fi
