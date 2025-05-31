#!/bin/bash

cd /src/assets/library
npm install
npx webpack

cp dist/xterm.mjs /src/src/components/lib/xterm.js/xterm.js

