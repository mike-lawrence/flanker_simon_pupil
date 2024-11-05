grp_to_tbl = function(grp,z){
	a = z$get_item(grp)
	attrs = a$get_attrs()$to_list()
	inputs_tbl = NULL
	if(!is.null(attrs$inputs)){
		inputs_tbl = attrs$inputs %>% as_tibble()
	}
	col_names = unlist(attrs$col_names)
	if(grp=='exp'){
		col_names = c(col_names[1:2],'trial_start_time',col_names[3:15])
	}
	mapping_list = attrs$col_info
	map_values_reversed <- function(column, mapping) {
		if (!is.null(mapping$mapping)) {
			# Reverse the mapping by switching names and values
			reversed_mapping <- setNames(names(mapping$mapping), mapping$mapping)
			factor(as.character(reversed_mapping[as.character(column)]))
		} else {
			column  # Return unchanged if no mapping is found
		}
	}
	(
		a$as.array()
		%>% as.data.frame()
		%>% set_names(col_names)
		%>% as_tibble()
		%>% mutate(
			across(
				everything()
				, ~map_values_reversed(.x, mapping_list[[cur_column()]])
			)
		)
		%>% bind_cols(inputs_tbl,.)
	)
}


process_zarr_file = function(zarr_file){
	#workaround for pizzarr's inability to directly parse .zarr.zip files
	tmp = tempfile()
	fs::dir_create(tmp)
	unzip(zarr_file, exdir=tmp)
	grps = fs::dir_ls(tmp) %>% fs::path_file()
	z = pizzarr::zarr_open(tmp)
	(
		grps
		%>% map(
			.f = function(grp){
				(
					grp_to_tbl(grp,z)
					%>% mutate(
						file = zarr_file %>% fs::path_dir() %>% fs::path_file()
					)
				)
			}
		)
		%>% set_names(grps)
	) ->
		tbls
	return(tbls)
}


