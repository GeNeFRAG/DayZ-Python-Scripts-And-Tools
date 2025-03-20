#!/bin/zsh

SRC_DIR="src/tools/item_tools"
DATA_FILE="data/json_loot.csv"
OUTPUT_DIR="../DayZ-CHERNARUS-PvPe-Bunker-Trader-Boosted-Loot-Server-For-Console/db"
TYPES_REF_XML="types_ref.xml"
TYPES_XML="types.xml"

python $SRC_DIR/types_to_excel.py --to-xml types_ref.xlsx $TYPES_REF_XML
python $SRC_DIR/sort_types_usage.py $TYPES_REF_XML $TYPES_REF_XML
python $SRC_DIR/sync_json_to_types.py $DATA_FILE $TYPES_REF_XML $TYPES_XML

cp $TYPES_REF_XML $TYPES_XML $OUTPUT_DIR

cd $OUTPUT_DIR
git add $TYPES_XML $TYPES_REF_XML
git commit -m "Update with latest changes"
git push