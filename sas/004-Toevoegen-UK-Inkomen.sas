libname UK xlsx '/sasdata/groups/PWC_Intern_SSBI/data/regionale-statistieken/UK_inkomen_2023.xlsx';
libname STAT '/sasdata/groups/PWC_Intern_SSBI/data/STAT';

options validvarname=v7;
data STAT.UK_Inkomen(rename=( Region_name=NUTS_Label) drop =ITL _2023);
    set UK."GDHI-Head"n;
    where ITL = 'ITL3';
    
    Inkomen = input(_2023,10.);

    if ITL_code = 'TLN06' then nuts3 = 'UKN06';
    else if ITL_code = 'TLN07' then nuts3 = 'UKN07';
    else if ITL_code = 'TLN08' then nuts3 = 'UKN08';
    else if ITL_code = 'TLN09' then nuts3 = 'UKN09';
    else if ITL_code = 'TLN0A' then nuts3 = 'UKN10';
    else if ITL_code = 'TLN0B' then nuts3 = 'UKN11';
    else if ITL_code = 'TLN0C' then nuts3 = 'UKN12';
    else if ITL_code = 'TLN0D' then nuts3 = 'UKN13';
    else if ITL_code = 'TLN0E' then nuts3 = 'UKN14';
    else if ITL_code = 'TLN0F' then nuts3 = 'UKN15';
    else if ITL_code = 'TLN0G' then nuts3 = 'UKN16';
    
    else if ITL_code = 'TLK51' then nuts3 = 'UKK11';
    else if ITL_code = 'TLK52' then nuts3 = 'UKK12';
    else if ITL_code = 'TLK73' then nuts3 = 'UKK13';
    else if ITL_code = 'TLK71' then nuts3 = 'UKK14';
    else if ITL_code = 'TLK72' then nuts3 = 'UKK15';
    else if ITL_code = 'TLK24' then nuts3 = 'UKK21';
    else if ITL_code = 'TLK25' then nuts3 = 'UKK22';
    else if ITL_code = 'TLK23' then nuts3 = 'UKK23';

    else if ITL_code = 'TLC31' then nuts3 = 'UKC11';
    else if ITL_code = 'TLC32' then nuts3 = 'UKC12';
    else if ITL_code = 'TLC33' then nuts3 = 'UKC13';
    else if ITL_code = 'TLC41' then nuts3 = 'UKC14';
    else if ITL_code = 'TLC42' then nuts3 = 'UKC21';
    else if ITL_code = 'TLC43' then nuts3 = 'UKC22';
    else if ITL_code = 'TLC44' then nuts3 = 'UKC23';

    else if ITL_code = 'TLD13' then nuts3 = 'UKD11';
    else if ITL_code = 'TLD14' then nuts3 = 'UKD12';

    else if ITL_code = 'TLE33' then nuts3 = 'UKE31';
    else if ITL_code = 'TLE34' then nuts3 = 'UKE31';
    else if ITL_code = 'TLE35' then nuts3 = 'UKE31';
    else if ITL_code = 'TLE32' then nuts3 = 'UKE32';

    else if ITL_code = 'TLH41' then nuts3 = 'UKH11';
    else if ITL_code = 'TLH42' then nuts3 = 'UKH12';

    else if ITL_code = 'TLH51' then ITL_code = 'TLH15';
    else if ITL_code = 'TLH52' then ITL_code = 'TLH16';
    else if ITL_code = 'TLH53' then ITL_code = 'TLH17';

    else if ITL_code = 'TLH61' then ITL_code = 'TLH14';
    else if ITL_code = 'TLH62' then ITL_code = 'TLH14';
    else if ITL_code = 'TLH63' then ITL_code = 'TLH14';
    else if ITL_code = 'TLH64' then ITL_code = 'TLH14';
    else if ITL_code = 'TLH14' then nuts3 = 'UKH14';

    else if ITL_code = 'TLI36' then nuts3 = 'UKI31';
    else if ITL_code = 'TLI35' then nuts3 = 'UKI32';

    else if ITL_code = 'TLJ15' then nuts3 = 'UKJ11';
    else if ITL_code = 'TLJ16' then nuts3 = 'UKJ11';

    else if ITL_code = 'TLL31' then nuts3 = 'UKL11';
    else if ITL_code = 'TLL32' then nuts3 = 'UKL12';
    else if ITL_code = 'TLL33' then nuts3 = 'UKL13';
    else if ITL_code = 'TLL42' then nuts3 = 'UKL14';
    else if ITL_code = 'TLL51' then nuts3 = 'UKL15';
    else if ITL_code = 'TLL53' then nuts3 = 'UKL16';
    else if ITL_code = 'TLL44' then nuts3 = 'UKL17';
    else if ITL_code = 'TLL43' then nuts3 = 'UKL18';
    else if ITL_code = 'TLL54' then nuts3 = 'UKL21';
    else if ITL_code = 'TLL52' then nuts3 = 'UKL22';
    else if ITL_code = 'TLL34' then nuts3 = 'UKL23';
    else if ITL_code = 'TLL41' then nuts3 = 'UKL24';

    else if ITL_code = 'TLM50' then nuts3 = 'UKL11';
    else if ITL_code = 'TLM03' then nuts3 = 'UKM71';
    else if ITL_code = 'TLM01' then nuts3 = 'UKM72';
    else if ITL_code = 'TLM11' then nuts3 = 'UKM73';
    else if ITL_code = 'TLM13' then nuts3 = 'UKM75';
    else if ITL_code = 'TLM12' then nuts3 = 'UKM76';
    else if ITL_code = 'TLM02' then nuts3 = 'UKM77';
    else if ITL_code = 'TLM14' then nuts3 = 'UKM78';
    else if ITL_code = 'TLM31' then nuts3 = 'UKM81';
    else if ITL_code = 'TLM32' then nuts3 = 'UKM82';
    else if ITL_code = 'TLM33' then nuts3 = 'UKM83';
    else if ITL_code = 'TLM34' then nuts3 = 'UKM84';
    else nuts3 = cat('UK', substr(ITL_code,3));

    if ITL_code = 'TLH14' then nuts3 = 'UKH14';
    if ITL_code = 'TLH15' then nuts3 = 'UKH15';
    if ITL_code = 'TLH16' then nuts3 = 'UKH16';
    if ITL_code = 'TLH17' then nuts3 = 'UKH17';
run;

proc sort data=STAT.uk_inkomen;
    by nuts3;
run;

proc sort data=STAT.NUTS_ZIP_NAME;
    by nuts3;
run;

data STAT.NUTS_ZIP_NAME(drop= ITL_code Inkomen);
    merge STAT.NUTS_ZIP_NAME STAT.UK_Inkomen;
    by nuts3;
    if inkomen ne . then Koopkracht = Inkomen;
run;
