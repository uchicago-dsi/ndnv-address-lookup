import { asyncBufferFromUrl, parquetReadObjects } from "hyparquet";
import { compressors } from "hyparquet-compressors";

export const getWaterData = async (
  url = new URL("/osm-water.parquet", import.meta.url).href
) => {
  const file = await asyncBufferFromUrl({ url });
  const water = await parquetReadObjects({ file, compressors });
  const waterGeoJSON = {
    type: "FeatureCollection",
    features: water.map((wet) => ({
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: wet.longitude.map((x, i) => [x, wet.latitude[i]]),
      },
      properties: {
        name: wet.name === null ? "" : wet.name,
        fclass: wet.fclass,
        area: wet.area,
      },
    })),
  };
  return waterGeoJSON;
};
