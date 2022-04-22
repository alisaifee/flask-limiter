#!/bin/bash

TAG=$(echo $GITHUB_REF | cut -d / -f 3)
git format-patch -1 $TAG --stdout | grep -P '^\+' | \
    sed '1,4d' | \
    grep -v "Release Date" | \
    sed -E -e 's/^\+(.*)/\1/' -e 's/^\*(.*)/## \1/' -e 's/^  //' -e 's/\:(.*)\:(.*)/\2/' | \
    sed -E -e 's/`(.*) <(https.*)>`_/[\1](\2)/'
