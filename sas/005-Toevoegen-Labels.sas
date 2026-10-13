libname STAT '/sasdata/groups/PWC_Intern_SSBI/data/STAT';
libname pwcfmt '/sasdata/groups/PWC_Intern_SSBI/data/format_library';

DATA fmt_input;
    SET stat.NUTS_ZIP_NAME;
    FMTNAME = 'nuts3_fmt';
    START   = nuts3;
    END     = nuts3;
    LABEL   = NUTS_label;
    TYPE    = 'C';
    drop nuts3 code country_code nuts_label koopkracht;
RUN;

proc sort data= fmt_input nodupkey;
    by start;
run;

proc format casfmtlib='pwcfmt' library=pwcfmt cntlin=fmt_input;
run;

proc format library=pwcfmt casfmtlib='pwcfmt';
    value $ country_fmt 'NL' = 'Nederland'
                        'DE' = 'Duitsland'
                        'ES' = 'Spanje'
                        'FR' = 'Frankrijk'
                        'GB' = 'Verenigd Koninkrijk'
                        'BE' = 'België';
run;

data stat.NUTS_ZIP_NAME;
    set stat.NUTS_ZIP_NAME;
    format  nuts3 $nuts3_fmt.
            country_code $country_fmt.;
run;

proc cas;
    sessionprop.promotefmtlib /
        fmtlibname="pwcfmt",
        replace=true;
run;
   sessionProp.listFmtLibs /              
      fmtLibName="pwcfmt",
      scope="global",
      showMemNames=true;
run;
quit;