/* Activeer alle beschikbare caslibs (o.a. voor autoload.dim_date) */
caslib _all_ assign;

/* ============================================================
   SCRIPT  : 010-import_naar_cas.sas
   DOEL    : Verwerking en verrijking van PWC consumentenorder-
             en adresdata. Koppeling met NUTS-koopkrachtdata en
             fiscale datumtabel. Segmentatie op productcategorie.
   OUTPUT  : public.pwc_consument_data
             public.pwc_lekue_consumenten
   ============================================================ */



/* Permanente library voor NUTS/koopkrachtdata */
libname STAT '/sasdata/groups/PWC_Intern_SSBI/data/STAT';

/* Bronbestanden: consumentenorders en adressenexport */
filename data  '/sasdata/groups/PWC_Intern_SSBI/data/20260513_consumer_export.csv';
filename adres '/sasdata/groups/PWC_Intern_SSBI/data/20260520_adresses_export.csv';
filename pkor '/sasdata/groups/PWC_Intern_SSBI/data/20260529_personeels_korting.csv';


/* Library voor formats */
libname library '/sasdata/groups/PWC_Intern_SSBI/data/format_library';

/* Sta underscores toe in variabelenamen (SAS v7-conventie) */
options validvarname = v7;

/* ------------------------------------------------------------
   STAP 1: Inlezen adresdata
   Gebruik guessingrows=20000 voor betrouwbare type-detectie
   bij grote of gevarieerde bestanden.
   ------------------------------------------------------------ */
proc import datafile=adres out=work.adresses_data dbms='csv' replace;
    guessingrows=MAX;
    delimiter=';';
run;

/* ------------------------------------------------------------
   STAP 2: Opschonen adresdata
   - Verwijder interne bronsysteemkolom (meta_src_code___)
   - Hernoem persoonssleutel naar uniforme naam
   - Converteer order_number_functional van numeriek naar
     karakter zodat de merge met consumentendata correct werkt
   ------------------------------------------------------------ */
data work.adresses_data(drop=meta_src_code evt_qty_returned rename=(prd_person_key_md5=master_person_key_md5));
    set work.adresses_data;
    /* Numeriek naar karakter om merge-conflicten te voorkomen */
    order_number_functional_c = strip(put(order_number_functional, best32.));
    drop order_number_functional;
    rename order_number_functional_c = order_number_functional;
run;

/* ------------------------------------------------------------
   STAP 3: CAS-tabellen opschonen
   Verwijder eventueel bestaande versies van de outputtabellen
   zodat aanmaak later in het script niet faalt.
   'quiet' onderdrukt een waarschuwing als de tabel niet bestaat.
   ------------------------------------------------------------ */
proc casutil;
    droptable casdata="pwc_consument_data"    incaslib="public" quiet;
    droptable casdata="pwc_lekue_consumenten" incaslib="public" quiet;
quit;

/* ------------------------------------------------------------
   STAP 4: Inlezen consumentendata
   ------------------------------------------------------------ */
proc import datafile=data out=work.consument_data dbms='csv' replace;
    guessingrows=MAX;
    delimiter=';';
run;

proc import datafile=pkor out=work.personeel_korting dbms='csv' replace;
    guessingrows=max;
    delimiter=';';
run;

data work.personeel_korting;
    set work.personeel_korting (rename=(order_number_functional=_order_num));
    order_number_functional = strip(put(_order_num, best32.));
    drop _order_num;
run;

/* Bestellingen met personeels korting moeten worden weggenomen */
proc sort data=work.consument_data;    by order_number_functional; run;
proc sort data=work.personeel_korting; by order_number_functional; run;

data work.consument_data;
    merge   consument_data      (in=a)
            personeel_korting   (in=b);
    by order_number_functional;
    if a and not b then output work.consument_data;
run;




/* Sorteren op samengestelde sleutel voor de merge in stap 5 */
proc sort data=work.adresses_data;      by master_person_key_md5 order_number_functional;        run;
proc sort data=work.consument_data;     by master_person_key_md5 order_number_functional;       run;

data work.consument_data;
    set work.consument_data;
    by master_person_key_md5 order_number_functional;
    if first.order_number_functional;
run;

/* ------------------------------------------------------------
   STAP 5: Samenvoegen consumentendata met adresdata
   Expliciete lengtes voorkomen truncatie bij langere waarden.
   'if b' = alleen records met een bekend adres worden bewaard;
   orders zonder adresrecord vallen weg.
   ------------------------------------------------------------ */
data work.consument_data_new;
    length prd_city     $ 28
           prd_zipcode  $ 14;
    merge work.consument_data  (in=a rename=(
              total_products_in_order        = _total_products_in_order
              orderline_sales                = _orderline_sales
              total_orders                   = _total_orders
              orderline_sales_after_discount = _orderline_sales_after_discount
              orderline_discount             = _orderline_discount
          ))
          work.adresses_data   (in=b);
    by master_person_key_md5 order_number_functional order_date;
    if a;

    net_sales                      = input(compress(net_sales_________, "'""`,"), NLMNLEUR8.2);
    total_products_in_order        = input(strip(_total_products_in_order), 8.);
    orderline_sales                = input(strip(_orderline_sales), NLMNLEUR8.2);
    total_orders                   = input(strip(_total_orders), 8.);
    orderline_sales_after_discount = input(strip(_orderline_sales_after_discount), NLMNLEUR8.2);
    orderline_discount             = input(strip(_orderline_discount), NLMNLEUR8.2);

    drop _total_products_in_order _orderline_sales
         _total_orders _orderline_sales_after_discount _orderline_discount
         net_sales_________ var21 var9;
run;

/* ------------------------------------------------------------
   STAP 6: Standaardisatie van land, postcode en gender
   - prd_zipcode  : witruimte verwijderen
   - prd_country  : naar hoofdletters; 'GB' -> 'UK' voor
                    aansluiting op de NUTS-koppeltabel
   - prd_gender   : naar hoofdletters en getrimd;
                    'F' -> 'V' (Nederlandstalige codering)
   ------------------------------------------------------------ */
data work.consument_data_new;
    set work.consument_data_new;
    prd_zipcode =trim(prd_zipcode);
    prd_zipcode =UPCASE(prd_zipcode);
    prd_city =trim(prd_city);
    prd_country = UPCASE(prd_country);
    if prd_country = 'GB' then prd_country = 'UK';
    prd_gender = UPCASE(trim(prd_gender));
    if prd_gender = 'F' then prd_gender = 'V';
run;


/* ------------------------------------------------------------
   STAP 7: Koppeling met NUTS-koopkrachtdata
   Match op postcode en land (beide moeten overeenkomen).
   Als het land niet overeenkomt krijgt NUTS3 de waarde 'N/A'.
   Voegt toe: NUTS3, koopkracht, NUTS_Label
   ------------------------------------------------------------ */
proc sql;
    create table work.consument_sorted_data_w_nuts as
    select
        cd.*,
        case
            when eun.country_code ne cd.prd_country then 'N/A'
            else eun.NUTS3
        end as NUTS3,
        eun.koopkracht,
        eun.NUTS_Label
    from work.consument_data_new as cd
    left join STAT.NUTS_ZIP_NAME as eun
        on cd.prd_zipcode = trim(eun.code) and cd.prd_country = eun.country_code
    order by cd.master_person_key_md5, order_number_functional;
quit;

/* 
Haal op welke postcodes foutief zijn



*/

/*  ophalen foute postcodes */
data work.foute_postcodes(keep=prd_zipcode prd_country);
    set work.consument_sorted_data_w_nuts;
    if nuts3 eq 'N/A' and prd_country in ('NL', 'BE','FR','DE','ES','UK') then output;
run;
/*  dedupliceren postcodes */
proc sort data=work.foute_postcodes nodupkey;
    by prd_zipcode;
run;
/*  matchen van delen van postcodes
    Als postcode 1010AZ niet bestaat gaan wij kijken naar mogelijke matches met 1010A%.
    Dit doen wij voor verschillende lengtes, van 7 t/m 4.
    Om niet nederlandse postcodes met spaanse te gaan vergelijken zit er een match op country_code bij.
*/
proc sql;
create table work._cand as
    select a.prd_zipcode,
           b.code as cand_code,
           b.country_code,
           b.nuts3,
           b.koopkracht,
           case
               when substr(a.prd_zipcode,1,7) = substr(b.code,1,7) then 7
               when substr(a.prd_zipcode,1,6) = substr(b.code,1,6) then 6
               when substr(a.prd_zipcode,1,5) = substr(b.code,1,5) then 5
               else 4
           end as match_len
    from work.foute_postcodes a
    inner join STAT.NUTS_ZIP_NAME b
        on substr(a.prd_zipcode,1,4) = substr(b.code,1,4)
       and a.prd_country = b.country_code;

create table work._best as
    select prd_zipcode, max(match_len) as match_len
    from work._cand
    group by prd_zipcode;

create table work._winner as
    select c.prd_zipcode, min(c.cand_code) as matched_code, b.match_len
    from work._cand c
    inner join work._best b
        on c.prd_zipcode = b.prd_zipcode and c.match_len = b.match_len
    group by c.prd_zipcode, b.match_len;

create table work.postcode_matched as
    select a.prd_zipcode,
           w.matched_code,
           
           case w.match_len
               when 7 then 'MATCH_7' when 6 then 'MATCH_6'
               when 5 then 'MATCH_5' when 4 then 'MATCH_4'
               else 'NO_MATCH'
           end as match_status,
           c.country_code,
           c.nuts3,
           c.Koopkracht
    from (select distinct prd_zipcode from work.foute_postcodes) a
    left join work._winner w on a.prd_zipcode = w.prd_zipcode
    left join work._cand   c on w.prd_zipcode = c.prd_zipcode
                             and w.matched_code = c.cand_code;
quit;

/* Het snelste is om een nieuwe tabel te maken */
proc sql;
    create table work.consument_with_nuts as
    select
        cd.*,
        coalesce(pm.nuts3, cd.NUTS3) as NUTS3_new,
        coalesce(pm.koopkracht,cd.koopkracht) as koopkracht_new
    from work.consument_sorted_data_w_nuts as cd
    left join work.postcode_matched as pm
        on cd.prd_zipcode = pm.prd_zipcode and cd.NUTS3 = 'N/A'
    order by cd.master_person_key_md5, order_number_functional;
quit;

data work.consument_with_nuts;
    set work.consument_with_nuts;
    if nuts3_new ne 'N/A'         then nuts3 = nuts3_new;
    if koopkracht_new ne .    then koopkracht = koopkracht_new;
    drop nuts3_new koopkracht_new;
run;

/* ------------------------------------------------------------
   STAP 8: Verwijder originele week- en jaarkolommen
   Deze worden in stap 10 vervangen door de fiscale definities
   conform de Brabantia-weeknummering (via dim_date).
   ------------------------------------------------------------ */
proc sql;
    alter table work.consument_with_nuts
    drop column week, year;
quit;



/* ------------------------------------------------------------
   STAP 9: Koppeling met fiscale datumtabel
   Vervangt de verwijderde week/jaar door fiscale equivalenten:
   - week_fisc -> week
   - year_fisc -> year
   Bron: autoload.dim_date, gekoppeld op order_date = date.
   ------------------------------------------------------------ */
proc sql;
    create table work.cons_data_w_date as
    select
        cd.*,
        d.week_fisc as week,
        d.year_fisc as year
    from work.consument_with_nuts as cd
    left join autoload.dim_date as d on cd.order_date = d.date;
quit;


/* ------------------------------------------------------------
   STAP 10: Eindtransformaties en wegschrijven
   Berekeningen:
   - Categoriecounts uit all_categories (waste_management t/m other)
   - Landcodering terugzetten: 'UK' -> 'GB' (ISO-standaard output)
   - Lege gender -> 'O' (Overig/Onbekend)
   - gender_encoded: M=1, V=2, O=3
   - age: leeftijd op moment van aankoop (0 als onbekend)
   - Fallback voor ontbrekende total_orders en net_sales

   Outputsplitsing:
   - lekue > 0  -> work.lekue_consument_data (Lekue-segment)
   - overig     -> public.pwc_consument_data (hoofdtabel, CAS)
   ------------------------------------------------------------ */
data public.pwc_consument_data(promote=yes) work.lekue_consument_data work.total_orders_too_high;
    set work.cons_data_w_date;

    /* Categoriecounts: tel hoe vaak elke categorie voorkomt in all_categories */
    length waste_management bathroom_toilet food_enjoyment laundry_caring service lekue other 8;
    waste_management = 0; bathroom_toilet = 0; food_enjoyment = 0;
    laundry_caring   = 0; service         = 0; lekue          = 0; other = 0;

    waste_management = count(all_categories, 'Waste Management');
    bathroom_toilet  = count(all_categories, 'Bathroom and Toilet');
    food_enjoyment   = count(all_categories, 'Food Enjoyment');
    laundry_caring   = count(all_categories, 'Laundry Caring');
    service          = count(all_categories, 'Service');
    lekue            = count(all_categories, 'Lékué');  /* Let op: exacte spelling vereist */
    other            = count(all_categories, 'other');
    _2024            = count(year, '2024');
    _2025            = count(year, '2025');


    /* Landcodering terug naar ISO-standaard voor extern gebruik */
    if prd_country = 'UK' then prd_country = 'GB';

    /* Onbekend gender expliciete waarde geven */
    if prd_gender = ' ' then prd_gender = 'O';

    /* Numerieke codering van gender voor modellen en analyses */
    gender_encoded = 0;
    if UPCASE(prd_gender) = 'M' then gender_encoded = 1;
    if UPCASE(prd_gender) = 'V' then gender_encoded = 2;
    if UPCASE(prd_gender) = 'O' then gender_encoded = 3;

    /* Leeftijd op aankoopdatum; 0 als geboortedatum ontbreekt */
    age = 0;
    if prd_birth_date ne '' or . then age = intck('year', prd_birth_date, order_date);

    /* Fallback voor ontbrekende ordertellingen en omzetwaarden */
    if total_orders = . then total_orders = 1;
    if missing(net_sales) or net_sales = 0  then net_sales    = orderline_sales_after_discount;


    /* format nuts3 $nuts3_fmt.;
    format prd_country $country_fmt.; */

    /* Splitsen: Lekue-orders apart, rest naar hoofdtabel */
    if lekue > 0 then output work.lekue_consument_data;
    else if total_orders>50 then output work.total_orders_too_high;

    else output public.pwc_consument_data;
run;

data public.pwc_consument_data;
    set public.pwc_consument_data;
    by master_person_key_md5;

 /* Initialiseer alle campagne-variabelen */
    retain outlet_jan_2024 droog_molen_actie refresh_steam_win design_your_bin
           droog_molen_promo_w26_2024 outlet_jul_2024 back_to_school
           bin_liner_promo outlet_jan_2025 droog_molen_promo_w10_2025
           droog_molen_promo_w20_2025 droog_molen_promo_w28_2025
           outlet_jul_2025 make_and_take newicon_win pink_lilac_strijkplank
           /* Seizoenen */
           post_holiday spring_sales back_to_school_season pre_holiday off_peak 0;

    /* Reset bij nieuwe klant */
    if first.master_person_key_md5 then do;
        outlet_jan_2024            = 0;
        droog_molen_actie          = 0;
        refresh_steam_win          = 0;
        design_your_bin            = 0;
        droog_molen_promo_w26_2024 = 0;
        outlet_jul_2024            = 0;
        back_to_school             = 0;
        bin_liner_promo            = 0;
        outlet_jan_2025            = 0;
        droog_molen_promo_2025     = 0;
        make_and_take              = 0;
        newicon_win                = 0;
        pink_lilac_strijkplank     = 0;
        outlet_jul_2025            = 0;
        /* Seizoenen */
        post_holiday               = 0;
        spring_sales               = 0;
        back_to_school_season      = 0;
        pre_holiday                = 0;
        off_peak                   = 0;
    end;

    /* 2024 campagnes */
    if year = 2024 and (week >= 1  and week <= 4)         then outlet_jan_2024            + 1;
    if year = 2024 and (week >= 15 and week <= 35)        then droog_molen_actie          + 1;
    if year = 2024 and (week >= 20 and week <= 21)        then refresh_steam_win          + 1;
    if year = 2024 and week = 23                          then design_your_bin            + 1;
    if year = 2024 and week = 26                          then droog_molen_promo_w26_2024 + 1;
    if year = 2024 and (week >= 27 and week <= 30)        then outlet_jul_2024            + 1;
    if year = 2024 and (week >= 33 and week <= 36)        then back_to_school             + 1;
    if year = 2024 and (week >= 40 and week <= 44)        then bin_liner_promo            + 1;

    /* 2025 campagnes */
    if year = 2025 and (week >= 1  and week <= 4)         then outlet_jan_2025            + 1;
    if year = 2025 and (week >= 10 and week <= 28)        then droog_molen_promo_2025     + 1;
    if year = 2025 and (week >= 27 and week <= 30)        then outlet_jul_2025            + 1;
    if year = 2025 and (week >= 33 and week <= 35)        then make_and_take              + 1;
    if year = 2025 and (week >= 37 and week <= 38)        then newicon_win                + 1;
    if year = 2025 and week = 50                          then pink_lilac_strijkplank     + 1;

    /* Seizoenen */
    if week >= 1  and week <= 4  then post_holiday           + 1;
    if week >= 10 and week <= 17 then spring_sales           + 1;
    if week >= 31 and week <= 39 then back_to_school_season  + 1;
    if week >= 44 and week <= 52 then pre_holiday            + 1;
    if week >= 5  and week <= 9  then off_peak               + 1;
    if week >= 18 and week <= 30 then off_peak               + 1;
    if week >= 40 and week <= 43 then off_peak               + 1;
run;


/* ------------------------------------------------------------
   STAP 11: Wegschrijven Lekue-consumenten naar CAS
   Gepromoveerde tabel beschikbaar voor alle CAS-sessies.
   ------------------------------------------------------------ */
data public.pwc_lekue_consumenten(promote=yes);
    set work.lekue_consument_data;
run;