{% macro generate_schema_name(custom_schema_name, node) -%}
    {#- Without this override, dbt-duckdb prefixes every custom schema
        with the target schema (e.g. "main_staging"). For a local,
        single-target project that's just noise — use the custom schema
        name directly, falling back to the target schema when none is
        set. -#}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
