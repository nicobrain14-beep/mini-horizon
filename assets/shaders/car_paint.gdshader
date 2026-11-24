shader_type spatial;
// Car paint for imported car models: the red areas of the source texture are the paint,
// recoloured to paint_color, with a glossy clear coat and metallic flakes under it.
// Everything else (trims, lights, badges) keeps the source texture.
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;   // glTF: G roughness, B metallic
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 paint_color : source_color = vec4(0.95, 0.72, 0.05, 1.0);
uniform float paint_metallic : hint_range(0.0, 1.0) = 0.55;
uniform float paint_roughness : hint_range(0.0, 1.0) = 0.38;
uniform float clearcoat_amount : hint_range(0.0, 1.0) = 1.0;
uniform float clearcoat_gloss : hint_range(0.0, 1.0) = 0.95;
uniform float flake_density = 900.0;        // flakes per UV unit
uniform float flake_strength : hint_range(0.0, 1.0) = 0.35;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

void fragment() {
	vec4 t = texture(albedo_tex, UV);
	vec4 orm = texture(orm_tex, UV);
	float paint = smoothstep(0.08, 0.25, t.r - max(t.g, t.b));
	float shade = clamp(t.r / 0.55, 0.0, 1.2);
	ALBEDO = mix(t.rgb, paint_color.rgb * shade, paint);
	// flakes fade out where they would be smaller than a pixel (no shimmer far away)
	vec2 fc = UV * flake_density;
	float fade = 1.0 - smoothstep(0.4, 1.2, length(fwidth(fc)));
	vec2 cell = floor(fc);
	float f = hash(cell);
	vec2 tilt = vec2(hash(cell + 1.3), hash(cell + 7.1)) - 0.5;
	METALLIC = mix(orm.b, paint_metallic, paint);
	ROUGHNESS = mix(orm.g, paint_roughness * (1.0 + (f - 0.5) * 0.6 * fade), paint);
	NORMAL = normalize(NORMAL + (TANGENT * tilt.x + BINORMAL * tilt.y) * flake_strength * 0.35 * paint * fade);
	NORMAL_MAP = texture(normal_tex, UV).rgb;
	CLEARCOAT = clearcoat_amount * paint;
	CLEARCOAT_ROUGHNESS = 1.0 - clearcoat_gloss;
}
