[out:json][timeout:60];
area["name"="Sugar Land"]["boundary"="administrative"]->.city;
way(area.city)["building"~"^(house|detached|semidetached_house|terrace|residential|apartments)$"];
out center tags;
