#!/bin/bash
cur=$(git rev-parse --abbrev-ref HEAD)
git checkout master
git push origin master --tags
git checkout 2.x
git merge master
git push origin 2.x
git checkout $cur
