cd "$HOME/actr7.x/examples/connections/nodejs"

if [ -n "$PORT" ]; then
  sed -i -e "s/http.listen(4000);/http.listen(process.env.PORT || 4000);/" environment.js
fi

node environment.js
