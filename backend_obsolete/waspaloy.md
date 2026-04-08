{
  "executive_summary": "This card consolidates Waspaloy (UNS N07001) billet data from producer datasheets (Special Metals, Carpenter, ATI), standards bodies (SAE AMS, ASTM, ISO, China SAMR OpenSTD), and peer‑reviewed hot‑deformation/emissivity studies. Key upgrades include: (i) authoritative designation links (UNS/AMS/ASTM/ISO; EU W.Nr); (ii) chemistry, density and melting range from producer bulletins; (iii) temperature tables for thermal conductivity, specific heat, CTE and elastic modulus from Carpenter; (iv) billet hot‑working guidance and avoid-regimes from Special Metals/ATI plus validated hot-compression processing windows and an Arrhenius hyperbolic‑sine constitutive model (Q=669.7 kJ/mol) from a peer‑reviewed study; (v) oxidized-surface emissivity behavior vs temperature from a peer‑reviewed machining/pyrometry study. Some requested national mappings (Japan JIS grade, Russia GOST grade, a specific Chinese GB grade-equivalence statement) were not found from accessible primary/official sources and are left null with notes.",
  "designation_table": [
    {
      "country_or_region": "USA",
      "system": "UNS",
      "designation": "UNS N07001",
      "primary_url": "https://www.carpentertechnology.com/hubfs/7407324/Material%20Saftey%20Data%20Sheets/Waspaloy.pdf",
      "notes": "Carpenter datasheet lists UNS N07001 under associated specifications.",
      "source_id": "S2"
    },
    {
      "country_or_region": "USA",
      "system": "SAE AMS",
      "designation": "AMS 5706 (bars/forgings/rings; Waspaloy chemistry basis)",
      "primary_url": "https://www.sae.org/standards/ams5706-alloy-bars-forgings-rings-corrosion-heat-resistant-nickel-base-195cr-135co-43mo-30ti-14al-solution-heat-treated-1825-1900-f-9961-10378-c-treatment-consumable-electrode-vacuum-induction-melted",
      "notes": "SAE AMS page provides the standard entry and scope for the Waspaloy-composition nickel alloy product forms.",
      "source_id": "S5"
    },
    {
      "country_or_region": "USA",
      "system": "ASTM",
      "designation": "ASTM B637 (precipitation-hardening nickel alloy bars/forgings/stock)",
      "primary_url": "https://www.astm.org/b0637-12.html",
      "notes": "ASTM listing page for B637; Waspaloy is commonly supplied under B637; producer bulletin lists ASTM B637 as applicable.",
      "source_id": "S12"
    },
    {
      "country_or_region": "Europe",
      "system": "Werkstoffnummer (W.Nr.)",
      "designation": "W.Nr. 2.4654",
      "primary_url": "https://www.specialmetals.com/documents/technical-bulletins/waspoloy.pdf",
      "notes": "Special Metals technical bulletin states Waspaloy is designated as UNS N07001 / W.Nr. 2.4654.",
      "source_id": "S1"
    },
    {
      "country_or_region": "International",
      "system": "ISO",
      "designation": "ISO 9725:2017 (nickel and nickel alloy forgings)",
      "primary_url": "https://www.iso.org/standard/69353.html",
      "notes": "ISO standard listing (forgings). Special Metals bulletin cites ISO 9725 as an applicable specification series for nickel alloy products.",
      "source_id": "S16"
    },
    {
      "country_or_region": "China",
      "system": "GB/T",
      "designation": "GB/T 40313-2021 (wrought superalloy forging disks)",
      "primary_url": "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=8D954836CA9D9BB95C0E661D4AEC7C7F",
      "notes": "Official SAMR OpenSTD entry for a national standard applicable to wrought superalloy forging disks. A specific GB grade equivalence label for Waspaloy was not found in accessible primary sources and is left null in the card.",
      "source_id": "S19"
    },
    {
      "country_or_region": "Japan",
      "system": "JIS",
      "designation": null,
      "primary_url": null,
      "notes": "Not found: an official JIS grade explicitly corresponding to Waspaloy (UNS N07001) from accessible primary sources.",
      "source_id": null
    },
    {
      "country_or_region": "Russia",
      "system": "GOST",
      "designation": null,
      "primary_url": null,
      "notes": "Not found: an official GOST grade explicitly corresponding to Waspaloy (UNS N07001) from accessible primary sources.",
      "source_id": null
    }
  ],
  "mermaid_flowchart": "flowchart TD\n  A[Start: target alloy = Waspaloy billet] --> B[Collect producer datasheets: Special Metals, Carpenter, ATI, Haynes]\n  B --> C[Extract designations listed by producers: UNS, W.Nr, applicable specs]\n  C --> D[Resolve standards-body pages for each spec: SAE AMS, ASTM, ISO]\n  D --> E[Collect national standards portals where available: China SAMR OpenSTD]\n  E --> F[Validate: designation appears in producer bulletin AND at least one standards-body/official portal]\n  F --> G[Extract property tables/curves: thermal, elastic, working ranges]\n  G --> H[Add peer-reviewed sources for flow stress & constitutive model]\n  H --> I[Add peer-reviewed source for oxidized-surface emissivity]\n  I --> J[Populate JSON card with per-field source_id mapping to source_index]\n  J --> K[Mark missing fields as null + 'not found']",
  "material_card": {
    "id": "WASPALOY_UNS_N07001_BILLET",
    "name": "Waspaloy",
    "object_type": "billet",
    "alloy_family": "Ni",
    "composition_family": "Ni-based superalloy",
    "aliases_standards": [
      {
        "system": "Trade name",
        "designation": "Waspaloy",
        "source_id": "S1"
      },
      {
        "system": "UNS",
        "designation": "N07001",
        "source_id": "S2"
      },
      {
        "system": "AISI",
        "designation": "AISI 685",
        "source_id": "S2"
      },
      {
        "system": "Werkstoffnummer",
        "designation": "2.4654",
        "source_id": "S1"
      },
      {
        "system": "SAE AMS",
        "designation": "AMS 5706",
        "source_id": "S5"
      },
      {
        "system": "SAE AMS",
        "designation": "AMS 5707",
        "source_id": "S6"
      },
      {
        "system": "SAE AMS",
        "designation": "AMS 5708",
        "source_id": "S7"
      },
      {
        "system": "SAE AMS",
        "designation": "AMS 5709",
        "source_id": "S8"
      },
      {
        "system": "SAE AMS",
        "designation": "AMS 5704 (forgings)",
        "source_id": "S9"
      },
      {
        "system": "SAE AMS",
        "designation": "AMS 5828 (welding wire/filler)",
        "source_id": "S10"
      },
      {
        "system": "ASTM",
        "designation": "ASTM B637",
        "source_id": "S12"
      },
      {
        "system": "ISO",
        "designation": "ISO 9723 (bars) / ISO 9724 (wire/drawing stock) / ISO 9725 (forgings)",
        "source_id": "S13"
      }
    ],
    "classification": {
      "microstructure": {
        "matrix_phase": "gamma_fcc",
        "features": [
          "gamma_prime_precipitates",
          "carbides"
        ],
        "notes": "Producer descriptions identify Waspaloy as precipitation hardening via γ′ from Al+Ti and additional strengthening from carbides at grain boundaries.",
        "source_id": "S3"
      },
      "strengthening_mechanisms": [
        "precipitation_hardening_gamma_prime",
        "solid_solution_strengthening",
        "carbide_grain_boundary_pinning"
      ],
      "composition_summary": {
        "base": "Ni",
        "major_alloying": [
          "Cr",
          "Co",
          "Mo",
          "Ti",
          "Al"
        ],
        "minor_additions": [
          "B",
          "Zr",
          "C"
        ],
        "notes": "Waspaloy is a Ni-base γ′-strengthened wrought superalloy; Cr/Co/Mo contribute to solid-solution strengthening and hot corrosion/oxidation resistance; Al+Ti form γ′; B/Zr/C support grain-boundary/carbine effects.",
        "source_id": "S1"
      },
      "processing_history": {
        "product_metallurgy": [
          "wrought",
          "VIM",
          "VAR_or_ESR"
        ],
        "typical_heat_treatments": [
          "solution_treat",
          "stabilize",
          "age"
        ],
        "notes": "ATI and Special Metals describe production via vacuum melting (VIM) followed by VAR/ESR and typical solution+stabilization+aging sequences.",
        "source_id": "S3"
      },
      "industrial_use": [
        "gas_turbine_rotating_parts",
        "compressor_disks",
        "turbine_disks",
        "shafts_spacers",
        "fasteners_high_temperature"
      ]
    },
    "chemistry": {
      "basis": "wt_percent",
      "nominal_or_limits": "limits",
      "elements": {
        "Ni": {
          "min": null,
          "max": null,
          "nominal": "balance",
          "source_id": "S2",
          "notes": "Nickel listed as Balance."
        },
        "Cr": {
          "min": 18.0,
          "max": 21.0,
          "nominal": null,
          "source_id": "S2"
        },
        "Co": {
          "min": 12.0,
          "max": 15.0,
          "nominal": null,
          "source_id": "S2"
        },
        "Mo": {
          "min": 3.5,
          "max": 5.0,
          "nominal": null,
          "source_id": "S2"
        },
        "Ti": {
          "min": 2.75,
          "max": 3.25,
          "nominal": null,
          "source_id": "S2"
        },
        "Al": {
          "min": 1.2,
          "max": 1.5,
          "nominal": null,
          "source_id": "S2"
        },
        "Fe": {
          "min": 0.0,
          "max": 2.0,
          "nominal": null,
          "source_id": "S2"
        },
        "Si": {
          "min": 0.0,
          "max": 0.75,
          "nominal": null,
          "source_id": "S2"
        },
        "Mn": {
          "min": 0.0,
          "max": 0.50,
          "nominal": null,
          "source_id": "S2"
        },
        "Zr": {
          "min": 0.02,
          "max": 0.12,
          "nominal": null,
          "source_id": "S2"
        },
        "C": {
          "min": 0.02,
          "max": 0.10,
          "nominal": null,
          "source_id": "S2"
        },
        "Cu": {
          "min": 0.0,
          "max": 0.10,
          "nominal": null,
          "source_id": "S2"
        },
        "S": {
          "min": 0.0,
          "max": 0.020,
          "nominal": null,
          "source_id": "S2"
        },
        "B": {
          "min": 0.003,
          "max": 0.008,
          "nominal": null,
          "source_id": "S2"
        },
        "P": {
          "min": null,
          "max": null,
          "nominal": null,
          "source_id": null,
          "notes": "Not found: phosphorus limits in the Carpenter datasheet table; Special Metals bulletin lists P max 0.030 wt%. If needed, use Special Metals limits.",
          "alternate_source_id": "S1"
        }
      }
    },
    "physical_properties": {
      "density": {
        "value": 8.19,
        "units": "g/cm^3",
        "temperature_C": 21,
        "source_id": "S1"
      },
      "solidus_temperature": {
        "value": 1330,
        "units": "C",
        "source_id": "S1",
        "notes": "Interpreted from melting range 1330–1360 °C as solidus–liquidus."
      },
      "liquidus_temperature": {
        "value": 1360,
        "units": "C",
        "source_id": "S1",
        "notes": "Interpreted from melting range 1330–1360 °C as solidus–liquidus."
      }
    },
    "thermal_properties": {
      "thermal_conductivity": {
        "table": {
          "units": "W/(m*K)",
          "data_points": [
            {
              "temperature_C": 21.1,
              "value": 11
            },
            {
              "temperature_C": 427,
              "value": 16
            },
            {
              "temperature_C": 649,
              "value": 20
            },
            {
              "temperature_C": 816,
              "value": 23
            },
            {
              "temperature_C": 982,
              "value": 26
            }
          ],
          "source_id": "S2",
          "notes": "Carpenter datasheet thermal conductivity table."
        }
      },
      "specific_heat": {
        "table": {
          "units": "kJ/(kg*K)",
          "data_points": [
            {
              "temperature_C": 93,
              "value": 0.52
            },
            {
              "temperature_C": 538,
              "value": 0.54
            },
            {
              "temperature_C": 649,
              "value": 0.55
            },
            {
              "temperature_C": 760,
              "value": 0.56
            },
            {
              "temperature_C": 871,
              "value": 0.58
            },
            {
              "temperature_C": 982,
              "value": 0.71
            }
          ],
          "source_id": "S2",
          "notes": "Mean specific heat values from Carpenter datasheet."
        }
      },
      "emissivity_oxidized_surface": {
        "table": {
          "units": "dimensionless",
          "measurement_band_or_method": "pyrometry-based emissivity coefficient; oxidizing/air heating causes matting/oxide",
          "data_points": [
            {
              "temperature_C": 400,
              "value": 0.24,
              "notes": "High-temperature pyrometer measurement reported in text."
            },
            {
              "temperature_C": 950,
              "value": 0.94,
              "notes": "High-temperature pyrometer measurement reported in text."
            }
          ],
          "source_id": "S18",
          "notes": "Peer-reviewed study reports strong increase of emissivity with temperature for Waspaloy in oxidizing conditions (oxide/matting), including 0.24 at 400°C and 0.94 at 950°C for one pyrometer configuration."
        }
      }
    },
    "elastic_properties": {
      "youngs_modulus_E": {
        "table": {
          "units": "GPa",
          "data_points": [
            {
              "temperature_C": 25,
              "value": 211.0
            },
            {
              "temperature_C": 260,
              "value": 200.6
            }
          ],
          "source_id": "S2",
          "notes": "Carpenter datasheet contains E table; only points visible in extracted lines are encoded here."
        },
        "constant_room_temperature": {
          "temperature_C": 21,
          "value": 211,
          "units": "GPa",
          "source_id": "S1",
          "notes": "Special Metals bulletin dynamic modulus at 70°F."
        }
      },
      "poissons_ratio_nu": {
        "value": null,
        "units": null,
        "source_id": null,
        "notes": "not found in accessible producer/standards/peer-reviewed sources used for this card"
      },
      "shear_modulus_G": {
        "value": null,
        "units": null,
        "source_id": null,
        "notes": "not found in accessible producer/standards/peer-reviewed sources used for this card"
      },
      "thermal_expansion_CTE": {
        "table": {
          "units": "1/K",
          "data_points": [
            {
              "temperature_range_C": [
                21,
                93
              ],
              "value": 12.2e-6,
              "notes": "Converted from 6.8×10^-6 in/in/°F."
            },
            {
              "temperature_range_C": [
                21,
                538
              ],
              "value": 13.9e-6,
              "notes": "Converted from 7.7×10^-6 in/in/°F."
            },
            {
              "temperature_range_C": [
                21,
                1093
              ],
              "value": 18.7e-6,
              "notes": "Converted from 10.4×10^-6 in/in/°F."
            }
          ],
          "source_id": "S1",
          "notes": "CTE ranges from Special Metals bulletin Table 2; SI conversions applied."
        }
      }
    },
    "hot_working": {
      "recommended_temperature_range_C": {
        "min": 980,
        "max": 1170,
        "source_id": "S1",
        "notes": "Special Metals: hot worked 1170–980°C; avoid cracking below 980°C and hot shortness above ~1180°C."
      },
      "recommended_strain_rate_range_s^-1": {
        "min": 0.01,
        "max": 1.0,
        "source_id": "S11",
        "notes": "Peer-reviewed hot compression processing-map study identifies optimum windows including low strain-rate regimes; full test range was 0.01–10 s^-1."
      },
      "processing_windows": [
        {
          "window_id": "W1_optimum_processing_map",
          "temperature_C_range": [
            1040,
            1120
          ],
          "strain_rate_s^-1_range": [
            0.01,
            0.01
          ],
          "goal": "uniform microstructure; avoid instability",
          "source_id": "S11"
        },
        {
          "window_id": "W2_optimum_processing_map",
          "temperature_C_range": [
            1080,
            1100
          ],
          "strain_rate_s^-1_range": [
            0.1,
            1.0
          ],
          "goal": "uniform microstructure; avoid instability",
          "source_id": "S11"
        }
      ],
      "instability_or_avoid_regions": [
        {
          "temperature_C_range": [
            1040,
            1120
          ],
          "strain_rate_s^-1_range": [
            1.5,
            10
          ],
          "notes": "Flow instability domain reported in processing map conclusions.",
          "source_id": "S11"
        },
        {
          "temperature_C_range": [
            1040,
            1080
          ],
          "strain_rate_s^-1_range": [
            0.02,
            0.1
          ],
          "notes": "Flow instability domain reported in processing map conclusions.",
          "source_id": "S11"
        },
        {
          "temperature_C_range": [
            1110,
            1120
          ],
          "strain_rate_s^-1_range": [
            0.02,
            0.3
          ],
          "notes": "Flow instability domain reported in processing map conclusions.",
          "source_id": "S11"
        }
      ],
      "difficulties": [
        {
          "issue": "rapid_work_hardening",
          "notes": "Intermediate anneals are normally required during cold working because the alloy work hardens very rapidly.",
          "source_id": "S1"
        },
        {
          "issue": "cracking_risk_below_hot_working_range",
          "notes": "Special Metals notes possible cracking below ~980°C during hot working.",
          "source_id": "S1"
        },
        {
          "issue": "hot_shortness_risk_above_upper_range",
          "notes": "Special Metals notes hot shortness above ~1180°C.",
          "source_id": "S1"
        },
        {
          "issue": "weldability_limited_strain_age_cracking",
          "notes": "ATI notes welding is difficult and susceptibility to cracking can require careful practice and re-solution + aging after weld/braze.",
          "source_id": "S3"
        }
      ],
      "mitigations": [
        {
          "action": "stay_within_hot_working_window",
          "notes": "Use 980–1170°C hot-working range (producer guidance) and prefer processing-map safe domains for uniform microstructure.",
          "source_id": "S1"
        },
        {
          "action": "apply_large_final_reductions_to_avoid_critical_strain",
          "notes": "ATI recommends final forging reductions large enough to prevent critical strains that lead to catastrophic grain growth during solution anneal.",
          "source_id": "S3"
        },
        {
          "action": "solution_treat_stabilize_age_after_hot_working_as_required",
          "notes": "Special Metals provides two common heat-treatment paths (creep/stress-rupture vs tensile optimized).",
          "source_id": "S1"
        }
      ]
    },
    "flow_stress": {
      "curves": [
        {
          "curve_id": "FS_WASPALOY_WANG2019_FIG2",
          "description": "True stress–true strain curves from isothermal compression across temperatures and strain rates (Waspaloy).",
          "conditions": {
            "temperature_C_range": [
              1000,
              1120
            ],
            "strain_rate_s^-1_range": [
              0.01,
              10
            ],
            "test_type": "isothermal_compression",
            "notes": "Curves shown in Figure 2 of the paper.",
            "source_id": "S11"
          },
          "data_points": null,
          "notes": "Graphical curves only; digitization required for point lists.",
          "source_id": "S11"
        }
      ],
      "constitutive_models": [
        {
          "model_type": "Arrhenius_hyperbolic_sine_peak_stress",
          "equation_text": "Z = \\dot\\varepsilon \\exp(Q/RT) = A\\,[\\sinh(\\alpha\\,\\sigma_p)]^n  (peak stress form); equivalently \\dot\\varepsilon = A\\,[\\sinh(\\alpha\\,\\sigma_p)]^n \\exp(-Q/RT).",
          "parameters": {
            "alpha_MPa^-1": 0.0041,
            "n": 4.35,
            "Q_kJ_per_mol": 669.7,
            "lnA": 58.34,
            "A_s^-1": 2.1714012036795453e+25,
            "n1": 5.72134,
            "beta_MPa^-1": 0.025946
          },
          "validity_ranges": {
            "temperature_C_range": [
              1000,
              1120
            ],
            "strain_rate_s^-1_range": [
              0.01,
              10
            ],
            "stress_definition": "peak_flow_stress_sigma_p"
          },
          "source_id": "S11",
          "notes": "Parameters extracted from the paper’s regression analysis text (alpha, n, lnA, Q)."
        }
      ]
    },
    "descriptions": {
      "short_description": {
        "text": "Waspaloy (UNS N07001 / W.Nr. 2.4654) is a Ni-base, age-hardenable wrought superalloy used for gas turbine and aerospace components requiring high strength and oxidation/corrosion resistance. Producer guidance indicates service up to ~650°C for critical rotating parts and up to ~870°C for less demanding conditions.",
        "source_id": "S1"
      },
      "metallurgical_notes": {
        "text": "High-temperature strength derives from solid-solution strengthening (Cr/Co/Mo) plus γ′ precipitation hardening from Ti+Al; carbides contribute by pinning grain boundaries and reducing grain-boundary sliding at elevated temperature.",
        "source_id": "S3"
      },
      "heat_treatment_practice": {
        "text": "Special Metals describes a common three-step sequence (solution, stabilization, aging) with variants optimized for creep/stress-rupture vs tensile properties; ATI also summarizes solution/stabilization/aging ranges.",
        "source_id": "S1"
      }
    },
    "data_status": "partial",
    "data_gaps": [
      {
        "field": "elastic_properties.poissons_ratio_nu",
        "reason": "not found in accessible producer/standards/peer-reviewed sources used"
      },
      {
        "field": "elastic_properties.shear_modulus_G",
        "reason": "not found in accessible producer/standards/peer-reviewed sources used"
      },
      {
        "field": "aliases_standards.JIS_designation",
        "reason": "not found in accessible primary sources"
      },
      {
        "field": "aliases_standards.GOST_designation",
        "reason": "not found in accessible primary sources"
      },
      {
        "field": "aliases_standards.China_GB_grade_equivalence_label",
        "reason": "not found from accessible primary/official sources during this pass"
      }
    ]
  },
  "source_index": [
    {
      "source_id": "S1",
      "title": "Special Metals Corporation — Technical Bulletin SMC-011: Waspaloy (UNS N07001 / W. Nr. 2.4654)",
      "url": "https://www.specialmetals.com/documents/technical-bulletins/waspoloy.pdf"
    },
    {
      "source_id": "S2",
      "title": "Carpenter Technology — WASPALOY Datasheet (type analysis, forms, physical/thermal/elastic tables)",
      "url": "https://www.carpentertechnology.com/hubfs/7407324/Material%20Saftey%20Data%20Sheets/Waspaloy.pdf"
    },
    {
      "source_id": "S3",
      "title": "ATI (Allegheny Technologies Incorporated) — ATI Waspaloy Alloy Technical Data Sheet (melting range, density, forging range, processing notes)",
      "url": "https://www.atimaterials.com/Products/Documents/datasheets/nickel-cobalt/nickel-based/ati_waspaloy_tds_en_v1.pdf"
    },
    {
      "source_id": "S4",
      "title": "Haynes International — HAYNES® Waspaloy alloy datasheet (general properties and application guidance)",
      "url": "https://haynesintl.com/wp-content/uploads/2024/08/waspaloy.pdf"
    },
    {
      "source_id": "S5",
      "title": "SAE International — AMS5706 standard entry (Nickel alloy bars/forgings/rings; Waspaloy chemistry basis)",
      "url": "https://www.sae.org/standards/ams5706-alloy-bars-forgings-rings-corrosion-heat-resistant-nickel-base-195cr-135co-43mo-30ti-14al-solution-heat-treated-1825-1900-f-9961-10378-c-treatment-consumable-electrode-vacuum-induction-melted"
    },
    {
      "source_id": "S6",
      "title": "SAE International — AMS5707 standard entry (Nickel alloy bars/forgings/rings; solution+stabilization+precipitation heat treated)",
      "url": "https://www.sae.org/standards/ams5707-alloy-bars-forgings-rings-corrosion-heat-resistant-nickel-base-195cr-135co-43mo-30ti-14al-solution-stabilization-precipitation-heat-treated-1825-1900-f-9961-10378-c-treatment-consumable-electrode-vacuum-induction-melted"
    },
    {
      "source_id": "S7",
      "title": "SAE International — AMS5708N standard entry (Waspaloy; bars/wire/forgings/rings; solution heat treated)",
      "url": "https://www.sae.org/standards/ams5708n-nickel-alloy-corrosion-heat-resistant-bars-wire-forgings-rings-forging-flash-welded-rings-heading-stock-58ni-195cr-135co-43mo-30ti-14al-005zr-0006b-waspaloy-consumable-electrode-vacuum-induction-melted-1975-f-1079-c-solution-heat-treated"
    },
    {
      "source_id": "S8",
      "title": "SAE International — AMS5709 standard entry (Waspaloy; bars/forgings; solution+stabilization+precipitation heat treated)",
      "url": "https://www.sae.org/standards/ams5709-alloy-bars-forgings-corrosion-heat-resistant-nickel-base-195cr-135co-43mo-30ti-14al-solution-stabilization-precipitation-heat-treated-1975-f-10794-c-treatment-consumable-electrode-vacuum-induction-melted"
    },
    {
      "source_id": "S9",
      "title": "SAE International — AMS5704 standard entry (Waspaloy forgings; solution+stabilization+precipitation heat treated)",
      "url": "https://www.sae.org/standards/ams5704-alloy-forgings-corrosion-heat-resistant-nickel-base-195cr-135co-43mo-30ti-14al-solution-stabilization-precipitation-heat-treated-1825-1900-f-9961-10378-c-treatment-consumable-electrode-vacuum-induction-melted"
    },
    {
      "source_id": "S10",
      "title": "SAE International — AMS5828 standard entry (Waspaloy welding wire/filler metal)",
      "url": "https://www.sae.org/standards/ams5828-alloy-wire-welding-corrosion-heat-resistant-nickel-base-195cr-135co-43mo-30ti-14al-vacuum-induction-melted"
    },
    {
      "source_id": "S11",
      "title": "Wang et al. — 'Investigation on the Thermal Deformation Behavior of the Nickel-Based Superalloy Strengthened by γ′ Phase' (Crystals, MDPI, 2019) — flow curves, processing maps, Arrhenius constitutive model parameters",
      "url": "https://www.mdpi.com/2073-4352/9/3/125"
    },
    {
      "source_id": "S12",
      "title": "ASTM International — B637 standard listing page (Precipitation-Hardening Nickel Alloy Bars, Forgings, and Forging Stock)",
      "url": "https://www.astm.org/b0637-12.html"
    },
    {
      "source_id": "S13",
      "title": "ISO — ISO 9723:1992 Nickel and nickel alloy bars (standard listing page)",
      "url": "https://www.iso.org/standard/17581.html"
    },
    {
      "source_id": "S14",
      "title": "ISO — ISO 9724:1992 Nickel and nickel alloy wire and drawing stock (standard listing page)",
      "url": "https://www.iso.org/standard/17582.html"
    },
    {
      "source_id": "S15",
      "title": "ISO — ISO 9725:1992 Nickel and nickel alloy forgings (standard listing page; withdrawn; links to 2017 edition)",
      "url": "https://www.iso.org/standard/17583.html"
    },
    {
      "source_id": "S16",
      "title": "ISO — ISO 9725:2017 Nickel and nickel alloy forgings (current standard listing page)",
      "url": "https://www.iso.org/standard/69353.html"
    },
    {
      "source_id": "S18",
      "title": "Kieruj, Przestacki, Chwalczuk — 'Determination of emissivity coefficient of heat-resistant super alloys and cemented carbide' (Archives of Mechanical Technology and Materials, Vol. 36, 2016; DOI:10.1515/amtm-2016-0006) — emissivity vs temperature including Waspaloy",
      "url": "https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-c62c0075-02f2-49d3-aac4-0571f57ba556/c/kieruj_przestacki_chwalczuk_determination_06_2016.pdf"
    },
    {
      "source_id": "S19",
      "title": "SAMR / SAC OpenSTD — GB/T 40313-2021 (Specification for wrought superalloy forging disks) standard metadata and official access page",
      "url": "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=8D954836CA9D9BB95C0E661D4AEC7C7F"
    }
  ]
}