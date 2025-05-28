import geopandas as gpd

OSM_PLACES_FILENAME = "~/Downloads/openstreetmap-ND/gis_osm_places_free_1.shp"

gpd.read_file(OSM_PLACES_FILENAME).query("name.notna()")[
    ["name", "fclass", "geometry"]
].to_file("public/osm-places.geojson", index=False)
