import { asyncBufferFromUrl, parquetReadObjects } from "hyparquet";
import { compressors } from "hyparquet-compressors";
import sourceList from "../data/source-list.json";

export const getAddressData = async (
  url = new URL("/911-addresses.parquet", import.meta.url).href
) => {
  const file = await asyncBufferFromUrl({ url });
  const addresses = await parquetReadObjects({ file, compressors });
  const addressesGeoJSON = {
    type: "FeatureCollection",
    features: addresses.map((addr) => ({
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [addr.lon, addr.lat],
      },
      properties: {
        num: addr.num,
        street: addr.street,
        muni: addr.muni,
        msag: addr.msag,
        zip: addr.zip,
        src_title: sourceList[addr.src].title,
        src_name: sourceList[addr.src].name,
        src_phone: sourceList[addr.src].phone,
        src_email: sourceList[addr.src].email,
      },
    })),
  };
  return addressesGeoJSON;
};
