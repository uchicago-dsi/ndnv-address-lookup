import { asyncBufferFromUrl, parquetReadObjects } from "hyparquet";
import { compressors } from "hyparquet-compressors";

export const getRoadData = async (
  url = new URL("/osm-roads.parquet", import.meta.url).href
) => {
  const file = await asyncBufferFromUrl({ url });
  const roads = await parquetReadObjects({ file, compressors });
  const roadsGeoJSON = {
    type: "FeatureCollection",
    features: roads.map((road, index) => ({
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: road.longitude.map((x, i) => [x, road.latitude[i]]),
      },
      properties: {
        name: road.name,
        fclass: road.fclass,
      },
    })),
  };
  return roadsGeoJSON;
};
