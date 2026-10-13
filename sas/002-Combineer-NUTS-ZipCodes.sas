proc import datafile='/sasdata/groups/PWC_Intern_SSBI/data/regionale-statistieken/pc2020_BE_NUTS-2021_v1.0.csv' dbms=csv out=BE_NUTS replace;
    delimiter=';';
run;
proc import datafile='/sasdata/groups/PWC_Intern_SSBI/data/regionale-statistieken/pc2020_DE_NUTS-2021_v4.0.csv' dbms=csv out=DE_NUTS replace;
    delimiter=';';
run;
proc import datafile='/sasdata/groups/PWC_Intern_SSBI/data/regionale-statistieken/pc2020_ES_NUTS-2021_v1.0.csv' dbms=csv out=ES_NUTS replace;
    delimiter=';';
run;
proc import datafile='/sasdata/groups/PWC_Intern_SSBI/data/regionale-statistieken/pc2020_FR_NUTS-2021_v2.0.csv' dbms=csv out=FR_NUTS replace;
    delimiter=';';
run;
proc import datafile='/sasdata/groups/PWC_Intern_SSBI/data/regionale-statistieken/pc2020_NL_NUTS-2021_v2.0.csv' dbms=csv out=NL_NUTS replace;
    delimiter=';';
run;
proc import datafile='/sasdata/groups/PWC_Intern_SSBI/data/regionale-statistieken/pc2020_UK_NUTS-2021_v.3.0.csv' dbms=csv out=UK_NUTS replace;
    delimiter=';';
run;



data work.NUTS_COMBINED;
    length code $14;
    set FR_NUTS UK_NUTS NL_NUTS ES_NUTS DE_NUTS BE_NUTS;

run;

libname STAT '/sasdata/groups/PWC_Intern_SSBI/data/STAT';

proc sort data= NUTS_COMBINED;
    by NUTS3;
run;

proc sort data = STAT.nuts3_names(rename=(NUTS_Code = NUTS3)) out=NUTS3_names;
    by NUTS3;
run;

data STAT.NUTS_ZIP_NAME;
    merge  NUTS_COMBINED NUTS3_names;
    by NUTS3;
    code = compress(code,' ');
    if code ne '' then output;
run;
