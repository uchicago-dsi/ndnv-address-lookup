import { asyncBufferFromUrl, parquetReadObjects } from "hyparquet";
import { compressors } from "hyparquet-compressors";

export const getRoadData = async (
  url = new URL("/osm-roads.parquet", import.meta.url).href
) => {
  const file = await asyncBufferFromUrl({ url });
  const roads = await parquetReadObjects({ file, compressors });
  const roadsGeoJSON = {
    type: "FeatureCollection",
    features: roads.map((road, index) => {
        const i = road.ref === null ? -1 : road.ref.indexOf(" ");
        let ref_prefix = "";
        let ref_rest = "";
        if (i != -1) {
            ref_prefix = road.ref.substring(0, i);
            ref_rest = road.ref.substring(i + 1);
        }
        return {
            type: "Feature",
            geometry: {
                type: "LineString",
                coordinates: road.longitude.map((x, i) => [x, road.latitude[i]]),
            },
            properties: {
                name: road.name,
                fclass: road.fclass,
                ref_prefix: ref_prefix,
                ref_rest: ref_rest,
                ref_length: road.ref === null ? 0 : road.ref.length,
                ref_rest_length: ref_rest.length,
                draw: road.draw,
            },
        };
    })
  };
  return roadsGeoJSON;
};
