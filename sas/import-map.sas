caslib _all_ assign;

proc import datafile='/sasdata/pwc/data/map/table_MAP_EU_NUTS.csv' out=work.EU_NUTS_MAP replace;
guessingrows=2000;
run;

proc casutil;
    droptable casdata="pwc_map_nuts"   incaslib="public" quiet;
quit;

data public.PWC_MAP_NUTS(promote=yes);
    set work.eu_nuts_map;
run;