/* Start CAS sessie */
cas casauto;
caslib _all_ assign;

/* STAP 0 */
proc casutil;
    droptable casdata="pwc_amount_of_orders"   incaslib="public" quiet;
    droptable casdata="pwc_person_addresses" incaslib="public" quiet;
    droptable casdata="pwc_aggregated"   incaslib="public" quiet;
    droptable casdata="pwc_concatenated" incaslib="public" quiet;
quit;

/* STAP 1 */
proc fedsql sessref=casauto;
    create table public.pwc_aggregated as
    select
        master_person_key_md5,
        sum(total_products_in_order) as total_products_in_order,
        sum(orderline_sales) as total_orderline_sales,
        count(order_number_functional) as order_number_functional_count,
        sum(waste_management) as total_waste_management,
        sum(bathroom_toilet) as total_bathroom_toilet,
        sum(food_enjoyment) as total_food_enjoyment,
        sum(laundry_caring) as total_laundry_caring,
        sum(service) as total_service,
        sum(other) as total_others,
        sum(_2024) as total_2024,
        sum(_2025) as total_2025,
        sum(outlet_jan_2024) as total_outlet_jan_2024,
        sum(droog_molen_actie) as total_droog_molen_2024,
        sum(refresh_steam_win) as total_steam_win,
        sum(design_your_bin) as total_design,
        sum(outlet_jul_2024) as total_outlet_jul_2024,
        sum(back_to_school) as total_back_to_school,
        sum(bin_liner_promo) as total_binliner,
        sum(outlet_jan_2025) as total_outlet_jan_2025,
        sum(droog_molen_promo_2025) as total_droog_molen_2025,
        sum(outlet_jul_2025) as total_outlet_jul_2025,
        sum(make_and_take) as total_make_take,
        sum(newicon_win) as total_newicon,
        sum(pink_lilac_strijkplank) as total_pink_strijkplank,
        sum(post_holiday) as total_post_holiday,
        sum(spring_sales) as total_spring_sales,
        sum(back_to_school_season) as total_back_to_school_season,
        sum(pre_holiday) as total_pre_holiday,
        sum(off_peak) as total_off_peak,

        case    when mean(net_sales) != 0 and mean(net_sales) is not null then mean(net_sales)
                else sum(orderline_sales)  
        end as net_sales,
        mean(Koopkracht) as koopkracht,
        mean(gender_encoded) as gender_encoded
    from public.pwc_consument_data
    group by master_person_key_md5;
quit;


/* STAP 2 */
data public.pwc_concatenated;
    set public.pwc_consument_data
        (keep=
            master_person_key_md5
            order_number_functional
            all_products_ordered
            all_attributes
            all_categories
            prd_country
         orderby=(master_person_key_md5));

    by master_person_key_md5;

    length
        order_number_functional_all $1600
        all_products_ordered_all    $3200
        all_attributes_all          $3200
        all_categories_all          $3200;

    retain
        order_number_functional_all
        all_products_ordered_all
        all_attributes_all
        all_categories_all;

    if first.master_person_key_md5 then do;
        order_number_functional_all = '';
        all_products_ordered_all    = '';
        all_attributes_all          = '';
        all_categories_all          = '';
    end;

    order_number_functional_all =
        catx('|', order_number_functional_all, order_number_functional);

    all_products_ordered_all =
        catx('|', all_products_ordered_all, all_products_ordered);

    all_attributes_all =
        catx('|', all_attributes_all, all_attributes);

    all_categories_all =
        catx('|', all_categories_all, all_categories);

    if last.master_person_key_md5 then output;

    keep
        master_person_key_md5
        order_number_functional_all
        all_products_ordered_all
        all_attributes_all
        all_categories_all
        prd_country;
run;




/* STAP 3 */
proc fedsql sessref=casauto;
    create table public.pwc_amount_of_orders as
    select
        a.master_person_key_md5,

        /* aggregaties */
        a.total_products_in_order,
        a.total_orderline_sales,
        a.order_number_functional_count,
        a.total_bathroom_toilet,
        a.total_food_enjoyment,
        a.total_waste_management,
        a.total_laundry_caring,
        a.total_service,
        a.total_others,
        a.total_2024,
        a.total_2025,
        a.net_sales,
        a.koopkracht,
        a.gender_encoded,
        a.total_outlet_jan_2024,
        a.total_droog_molen_2024,
        a.total_steam_win,
        a.total_design,
        a.total_outlet_jul_2024,
        a.total_back_to_school,
        a.total_binliner,
        a.total_outlet_jan_2025,
        a.total_droog_molen_2025,
        a.total_outlet_jul_2025,
        a.total_make_take,
        a.total_newicon,
        a.total_pink_strijkplank,
        a.total_post_holiday,
        a.total_spring_sales,
        a.total_back_to_school_season,
        a.total_pre_holiday,
        a.total_off_peak,

        /* concatenaties */
        b.order_number_functional_all,
        b.all_products_ordered_all,
        b.all_attributes_all,
        b.all_categories_all,
        b.prd_country
    from public.pwc_aggregated a
    left join public.pwc_concatenated b
        on a.master_person_key_md5 = b.master_person_key_md5;
quit;

/* STAP 4 */
proc fedsql sessref=casauto;
    create table public.pwc_person_addresses as
    select distinct
        master_person_key_md5,
        prd_gender,
        prd_birth_date,
        prd_zipcode,
        prd_city,
        prd_country,
        /* net_sales, */
        NUTS3,
        Koopkracht,
        NUTS_label,
        gender_encoded/*,*/
        /* age,
        week,
        year */
    from public.pwc_consument_data;
quit;

/* STAP 5 */
proc casutil;
    promote
        casdata="pwc_amount_of_orders"
        incaslib="public"
        outcaslib="public";

    promote
        casdata="pwc_person_addresses"
        incaslib="public"
        outcaslib="public";
quit;


/* STAP 6 */
proc casutil;
    droptable casdata="pwc_aggregated"   incaslib="public" quiet;
    droptable casdata="pwc_concatenated" incaslib="public" quiet;
    /* droptable casdata="pwc_joined_dataset" incaslib="public" quiet; */
quit;

/* 

proc fedsql sessref=casauto;
    create table public.pwc_joined_dataset as
    select a.*, 
        b.prd_gender,
        b.prd_birth_date,
        b.prd_zipcode,
        b.prd_city,
        b.prd_country,
        b.net_sales,
        b.NUTS3,
        b.Koopkracht,
        b.NUTS_label,
        b.gender_encoded,
        b.age,
        b.week,
        b.year -- doesnt exist
    from public.pwc_amount_of_orders a
    left join public.pwc_person_addresses b
        on a.master_person_key_md5 = b.master_person_key_md5;
quit;

proc casutil;
    promote
        casdata="pwc_joined_dataset"
        incaslib="public"
        outcaslib="public";
quit; */

proc fedsql sessref=casauto;
    select *
    from public.pwc_amount_of_orders
    where total_products_in_order > 100
    order by net_sales desc;
quit;


/* See each distinct value and how often it appears */
proc fedsql sessref=casauto;
    select net_sales, count(*) as frequency
    from public.pwc_amount_of_orders
    where net_sales>10000
    group by net_sales
    order by net_sales desc;
quit;


proc freq data=public.pwc_amount_of_orders;
    tables total_outlet_jul_2025 /nocum;

run;