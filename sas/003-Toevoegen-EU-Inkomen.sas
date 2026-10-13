libname EU xlsx '/sasdata/groups/PWC_Intern_SSBI/data/regionale-statistieken/EU_PPS_2023.xlsx';
libname STAT '/sasdata/groups/PWC_Intern_SSBI/data/STAT';

options validvarname=v7;
data STAT.EU_PPS(rename=(GEO__Codes_=Nuts3 GEO__Labels_=GEO_Labels PPS=Koopkracht));
    set EU."Sheet 1"n;
run;

data STAT.EU_PPS;
    set STAT.EU_PPS;
    if nuts3 = 'NL115' then nuts3 = 'NL113';
    if nuts3 = 'NL114' then nuts3 = 'NL111';
    if nuts3 = 'NL127' then nuts3 = 'NL124';
    if nuts3 = 'NL128' then nuts3 = 'NL125';
    if nuts3 = 'NL350' then nuts3 = 'NL310';
    if nuts3 = 'NL32A' then nuts3 = 'NL324';
    if nuts3 = 'NL32B' then nuts3 = 'NL329';
    if nuts3 = 'NL361' then nuts3 = 'NL332';
    if nuts3 = 'NL362' then nuts3 = 'NL333';
    if nuts3 = 'NL363' then nuts3 = 'NL337';
    if nuts3 = 'NL364' then nuts3 = 'NL33A';
    if nuts3 = 'NL365' then nuts3 = 'NL33B';
    if nuts3 = 'NL366' then nuts3 = 'NL33C';
    if nuts3 = 'NL415' then nuts3 = 'NL412';
    if nuts3 = 'NL416' then nuts3 = 'NL413';

    if nuts3 = 'DEG0S' then nuts3 = 'DEG04';
    if nuts3 = 'DEG0Q' then nuts3 = 'DEG0B';
    if nuts3 = 'DEG0T' then nuts3 = 'DEG0F';
    if nuts3 = 'DEG0V' then nuts3 = 'DEG0H';
    if nuts3 = 'DEG0U' then nuts3 = 'DEG0I';
    if nuts3 = 'DEG0R' then nuts3 = 'DEG0P';
run;

proc sort data=STAT.EU_PPS;
    by nuts3;
run;

data STAT.NUTS_ZIP_NAME(drop= nuts_level GEO_Labels);
    merge STAT.NUTS_ZIP_NAME STAT.EU_PPS;
    by nuts3;
    if code ne '' then output;
run;