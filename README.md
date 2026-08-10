# act-r-container
Code to build a Docker container with ACT-R in it along with the Node.js server running to support the HTML versions of the ACT-R Environment and experiment window viewer.

## Docker Compose

The default compose service starts the ACT-R container without Jupyter. It exposes the ACT-R remote interface on port 2650 and the existing HTML ACT-R Environment on port 4000:

```sh
docker compose up --build act-r
```

Then open the HTML environment at http://localhost:4000, or connect another process to the ACT-R remote interface at localhost:2650.

The Jupyter notebook interface is optional and runs under a compose profile:

```sh
docker compose --profile jupyter up --build jupyter
```

That exposes Jupyter at http://localhost:8888. Its ACT-R and HTML ports are mapped to localhost:2651 and http://localhost:4001 by default so it can run beside the default service without port conflicts.

The port mappings can be changed with environment variables:

```sh
ACTR_REMOTE_PORT=12650 ACTR_HTML_PORT=14000 docker compose up --build act-r
JUPYTER_PORT=18888 docker compose --profile jupyter up --build jupyter
```

## Heroku

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://www.heroku.com/deploy?template=https://github.com/CogTool-Modern/act-r-container/tree/feature/docker-image-actr-environment)

The included `heroku.yml` builds the `Dockerfile` as a Heroku `web` process and starts ACT-R in non-interactive web mode:

```sh
heroku create --stack container
git push heroku main
```

For an existing app, set the container stack before pushing:

```sh
heroku stack:set container
git push heroku main
```

Heroku exposes one assigned HTTP `$PORT`, so this deploy targets the HTML ACT-R Environment. The raw ACT-R TCP interface on port 2650 is not exposed through Heroku's HTTP router; use a host that supports arbitrary TCP services if external access to that port is required.

For forks, Heroku also supports a repo-agnostic button target of `https://www.heroku.com/deploy`, but that relies on GitHub sending a `Referer` header and can land on Heroku's unsupported button page when the repo cannot be inferred.

Below are four ways that one could use this without having to rebuild the container.  The first two work online without needing to install any software using the mybinder and Play with Docker free services, and the other two require that one installs the Docker software.  If you have the Docker software you could also use these sources to build a custom version that includes additional models, notebooks, servers, etc.

1) From mybinder.org (or other BinderHub) to run ACT-R from Python in Jupyter notebooks without any local installation necessary.
There are Jupyter notebooks with some simple examples of running the tutorial models, and this button will start it [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/db30/act-r-container/main?filepath=tutorial.ipynb).


2) You can run the Lisp prompt interface of ACT-R using the Play with Docker site: https://labs.play-with-docker.com/, and you will also have access to the HTML version of the ACT-R Environment and experiment window viewer.  There is also an editor available in the Play with Docker interface which will allow you to work with the included ACT-R model and code files, but it will not store those files locally (you could cut-and-paste from the Play with Docker editor to a local file if you wanted to save them).

To run it, after starting a new session on Play with Docker you can call this from the prompt:

docker pull db30/act-r-container

Then

docker run -i -p 4000:4000 db30/act-r-container act-r.sh

Clicking on the 4000 at the top of the window will open the ACT-R Environment, and the "Open Experiment Window" button will open a window with the experiment window viewer.

3) You can use this to run ACT-R on a machine which has Docker installed to avoid having to install a Lisp, quicklisp, and the ACT-R code.
If you run it as shown below then you can also connect to the HTML version of the ACT-R Environment and experiment window viewer, connect Python (or other remote interface) to it on the default ACT-R port (2650), and have the tutorial files copied from inside the container to a directory on the local machine where they can be editted and still accessed by ACT-R which is inside the container from its actr7.x/tutorial directory.
There is an image already built on DockerHub so you can get it with this:

docker pull db30/act-r-container

Then you can run it like this which will leave you at a Lisp prompt (in SBCL) ready to go:

Mac and Linux

docker run -i -p 4000:4000 -p 2650:2650 -v ~/act-r-tutorial:/home/actr/actr7.x/tutorial db30/act-r-container

Windows

docker run -i -p 4000:4000 -p 2650:2650 -v %homedrive%%homepath%\act-r-tutorial:/home/actr/actr7.x/tutorial db30/act-r-container

The -p flags are to expose the ports for the HTML Environment interface and the ACT-R remote interface respectively.  The -v flag sets up the location on the computer where the tutorial files will be stored.  The value before the : is the path on the local machine to the files.  It can be anywhere, and will create the directory if it does not already exist, but it is safest to create it in advance because when it gets created by docker it may not have the proper permissions for the current user.  The example calls above create an act-r-tutorial directory in the user's home directory, and it won't overwrite any files already in that directory on the computer so you can safely work on those files across different runs of the container.

The ACT-R Environment will be available from a browser at: http://localhost:4000 and the experiment window viewer at: http://localhost:4000/expwindow.html or by clicking the "Open Experiment Window" button in the Environment.

Note, if you're using MacOS and working with ACT-R from another language, my experience is that it's faster to use this containered version than it is to run a Lisp locally on the machine!  That's because SBCL is faster than other Lisps, but the MacOS native version of SBCL has some threading or locking performance issues (not entirely sure which).  The SBCL in the container doesn't suffer from those issues, and the container overhead was less costly on my machine than those issues.

4) Because the container contains a Jupyter notebook server you can run it similar to the first option locally on a machine i.e. the Python connection through the Jupyter notebooks.  This is very similar to the previous one, but you would want to run it like this:

Mac and Linux

docker run -i -p 4000:4000 -p 2650:2650 -p 8888:8888 -v ~/act-r-tutorial:/home/actr/actr7.x/tutorial db30/act-r-container run-jupyter.sh

Windows

docker run -i -p 4000:4000 -p 2650:2650 -p 8888:8888 -v %homedrive%%homepath%\act-r-tutorial:/home/actr/actr7.x/tutorial db30/act-r-container run-jupyter.sh

The -p 8888:8888 exposes the port for the Jupyter notebook server.  Once it finishes starting and is ready it will display some links that you can copy into a browser to connect to the server and access the notebooks.
