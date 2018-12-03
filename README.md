# dotcomb
Combines Doxygen generated Graphviz collaboration graphs into larger ones. Doxygen generates collaboration graphs for single classes only. This means
that it does not show a full picture of the hierarchy. This tool should be language independent as long as collaboration charts make any
sense with the language.

This script reads all the dot files recursively under a directory, reads all
the edge and node information from them, combines nodes with the same name and
otherwise cleans up (by e.g. removing nodes with no edges). Nodes can also be
clustered into subgraphs and output filtered both with regular expression
patterns and exact matches (such as removing the String class).

This is a combined collaboration graph. It does not include things like
function calls so that sort of dependencies will be lacking. It will include
inheritance hierarchy and collaborative links. The latter means classes used
by a class in an attribute ("OtherClasss other").

See the example file (chromium.png) for an example.

## Requiremens
* Python3
* PyYAML
* Doxygen
* Graphviz

## Usage

Edit the supplied Doxyfile to suit your needs but make sure HAVE_DOT and
COLLABORATION_GRAPH settings are set to YES and DOT_CLEANUP to NO.

Use this Doxyfile to generate the documentation. After that run 

    for i in `find . -name "*__coll*.dot` | do dot -Tcanon -o /tmp/project/dots$(basename $i) $i; done

This will collect all the collaboration graph definitions into one place and convert them into canonical form which is easier to handle. You can obviously use any output directory. 

After this all that is needed is to run this tool:

    ./dotcomb.py -f -d /tmp/project/ > output.dot

And finally generate the image:

    dot -Tpng -o collaboration.png output.dot

settings.yaml includes a number of settings that can be used to alter the
output, mostly for setting colours. You might also want to use svg for large
images.

Use the -h parameter to get a list of command-line parameters.

## Example

chromium.dot and chromium.png include an example picked from Android Open
Source Project. These files were created from
chrome/android/java/src/org/chromium directory using the settings in
settings.yaml. This is obviously just a quick example with more or less
randomly selected components used for demontstrating component highlightning.
You can add any number of colours (as long as each component can be
distinguished with the same regular expression pattern) as well as filter rules.
