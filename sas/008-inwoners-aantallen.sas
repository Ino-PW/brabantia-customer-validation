caslib _all_ assign;
options validvarname=v7;

proc import datafile='/sasdata/pwc/data/regionale-statistieken/inwoners-aantallen-nuts3-UK-2019.xlsx'
    out=work.uk_raw
    dbms=xlsx
    replace;
    getnames=yes;
    sheet='Sheet 1';

run;

proc import datafile='/sasdata/pwc/data/regionale-statistieken/inwoners-aantallen-nuts3-5eu-landen.xlsx'
    out=work.eu_raw
    dbms=xlsx
    replace;
    getnames=yes;
    sheet='Sheet 1';
run;

proc contents data=work.eu_raw; run;
proc contents data=work.uk_raw; run;

data work.eu_raw;
    set work.eu_raw;
    if Total_2024 eq . then Total_2024 = Total_2021;
    if Y_LT15_2024 eq . then Y_LT15_2024 = Y_LT15_2021;
    if Y15_64_2024 eq . then Y15_64_2024 = Y15_64_2021;
    if Y_GE65_2024 eq . then Y_GE65_2024 = Y_GE65_2021;
    rename  Total_2024 = total
            Y_LT15_2024      = less_than_15_years
            Y15_64_2024     = from_15_to_64_years
            Y_GE65_2024 = _65_years_or_over;
run;


%macro fix_types(ds);
data work.&ds.;
    set work.&ds.;
    total_n             = input(strip(total),              commax20.);
    less_than_15_n      = input(strip(less_than_15_years),  commax20.);
    from_15_to_64_n     = input(strip(from_15_to_64_years), commax20.);
    _65_years_or_over_n = input(strip(_65_years_or_over),   commax20.);
    drop total less_than_15_years from_15_to_64_years _65_years_or_over;
    rename total_n             = total
           less_than_15_n      = less_than_15_years
           from_15_to_64_n     = from_15_to_64_years
           _65_years_or_over_n = _65_years_or_over;
run;
%mend fix_types;

%fix_types(eu_raw);
%fix_types(uk_raw);

data work.inwoners_aantallen(rename=(geo__labels_ = Labels GEO__Codes_ = NUTS3));
    length geo__labels_ $85.;
    length GEO__Codes_ $20.;
    set uk_raw eu_raw;
    geo__codes_ = strip(geo__codes_);
    geo__labels_ = strip(substr(geo__labels_, 1, index(geo__labels_, '(NUTS') - 1));

    if total ne . then output;
    drop total_2021 Y_LT15_2021 Y15_64_2021 Y_GE65_2021 unknown D F H J;
run;


proc casutil;
    droptable casdata="pwc_inwoners_aantallen" incaslib="public" quiet;
quit;


data public.pwc_inwoners_aantallen(promote=yes);
    set work.inwoners_aantallen;
run;