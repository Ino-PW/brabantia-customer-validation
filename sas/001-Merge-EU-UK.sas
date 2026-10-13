libname xl xlsx '/sasdata/groups/PWC_Intern_SSBI/data/regionale-statistieken/NUTS2021-NUTS2024.xlsx';
libname UK xlsx '/sasdata/groups/PWC_Intern_SSBI/data/regionale-statistieken/UK-NUTS.xlsx';

libname STAT '/sasdata/groups/PWC_Intern_SSBI/data/STAT';

options validvarname=v7;
data NUTS3_EU(drop=NUTS_level_3____italics__NUTS_20 _ Code_2021 Code_2024 NUTS_level_1____italics__NUTS_20 NUTS_level_2____italics__NUTS_20  change country_order Region_order__NUTS_2021_ Region_order__NUTS_2024_);
    set xl."NUTS2021- NUTS2024"n;
    NUTS_code = Code_2021;
    NUTS_Label = coalescec(NUTS_level_1____italics__NUTS_20,NUTS_level_2____italics__NUTS_20,NUTS_level_3____italics__NUTS_20);

    if country_code in ('NL' 'DE' 'ES' 'FR' 'BE') then output;
run;

data NUTS3_UK(rename=(nuts_3_code = NUTS_Code NUTS_3_name=NUTS_label));
    set UK."NUTS 3"n;
    country_code = 'UK';
    NUTS_level = 3;
run;

data STAT.NUTS3_Names;
    set NUTS3_EU NUTS3_UK;

run;


    