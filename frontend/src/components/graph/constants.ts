export const VIEW_ANIM = {
  easing: "ease-in-out" as const,

  fit: {
    duration: 400,
    padding: 30,
  },

  center: {
    duration: 500,
    minZoom: 1.0,
    paddingIfNoSelection: 30,
  },

  zoom: {
    duration: 250,
    factor: 1.15,
  },

  layout: {
    duration: 450,
    fitDuration: 350,
    padding: 80,
    spacing_factor: 2.6,
  },
} as const;
