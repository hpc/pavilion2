class TestConfig:

    def __init__(self, config, var_man=None):
        """
        :param config:
        :param var_man:
        """
        self._config = config
        self._var_man = var_man

    @property
    def scheduler_section(self):

        self._config.get('scheduler')



    def get_result_locations(self):
        rl = []
        for k, v in self.ecf.iteritems():
            if not isinstance(v, dict):
                continue
            te = TestEntry(k, v, None)
            res_loc = te.get_results_location()
            # no need to repeat the location
            if res_loc not in rl:
                rl.append(res_loc)
        return rl

    def show_user_test_config(self):
        """
        Display the users test config file
        """
        print json.dumps(self.user_config_doc, sort_keys=True, indent=4)

    def show_default_config(self):
        """
        Display the system default test config file
        """
        print json.dumps(self.default_config_doc, sort_keys=True, indent=4)

    def create_effective_config_file(self, override_cf="", default_cf=""):
        """
        Return the complete test suite file to be used for this test
        after it is folded in with the default configuration
        """

        if override_cf == "":
            override_cf=self.user_config_doc
        else:
            override_cf=self.load_config_file( override_cf )

        if default_cf == "":
            default_cf=self.default_config_doc
        else:
            default_cf=self.load_config_file( default_cf )

        # get a copy of the default configuration for a test
        _, default_config = default_cf.items()[0]

        # then, for each new test entry (stanza) in the user_config_doc
        # merge with the default entry (overriding the defaults)
        new_dict = {}
        for test_id, v in override_cf.items():
            # only use "good" entries
            if isinstance(v, dict):
                if not TestEntry.check_valid(v):
                    print ", skipping stanza (%s) due to invalid entry" % test_id
                    continue
            tmp_config = default_config.copy()

            # merge the user dictionary with the default configuration. Tried
            # other dict methods ( "+", chain, update) and these did not work with nested dict.
            new_dict[test_id] = merge(tmp_config, override_cf[test_id])

        return new_dict

    def get_effective_config_file(self):
        return self.ecf

    def show_effective_config_file(self):
        """
        Display the effective config file
        """
        #ecf = self.get_effective_config_file()
        print json.dumps(self.ecf, sort_keys=True, indent=4)

    def extract_nested_tests( self, test_suite ):
        """
        This method should recursively check for the 'IncludeTestSuite' key in each
        successive test suite and expand it into a single test suite.
        """
        if not isinstance( test_suite, dict ):
            error_msg = "Loaded test suite is not well-formed."
            self.logger.error( error_msg )
            sys.exit(error_msg)

        ret_dict = {}

        if "IncludeTestSuite" in test_suite.keys():
            for testfile in test_suite['IncludeTestSuite']:
                if len(testfile) >= 5 and testfile[-5:] != ".yaml":
                    testfile += ".yaml"
                elif len(testfile) < 5:
                    testfile += ".yaml"
                try:
                    ret_dict[testfile[:-6]] = self.load_config_file(testfile)
                    tmp_dict = self.extract_nested_tests( ret_dict[testfile[:-6]] )
                    if tmp_dict != {}:
                        for testname, test in tmp_dict.iteritems():
                            ret_dict[testname] = test
                        del ret_dict[testfile[:-6]]
                except:
                    error_msg = "Test file included by 'IncludeTestSuite' key could not be loaded."
                    self.logger.error( error_msg )
                    sys.exit(error_msg)

        return ret_dict

    def find_expansions( self, test ):
        """
        This function will crawl through a test and try to find lists that need to be
        expanded into individual tests.
        """

        if not isinstance( test, dict ):
            error_msg = "Object provided to find_expansions function is not of type dict."
            self.logger.error( error_msg )
            sys.exit( error_msg )

        for t_key, t_val in test.iteritems():
            if isinstance( t_val, dict ):
                name, target = self.find_expansions( t_val )
                if target == ["empty"]:
                    return "empty", ["empty"]
                else:
                    ret_key = t_key + '.' + name
                    return ret_key, target
            elif isinstance( t_val, list ) and len( t_val ) != 0:
                return t_key, t_val
            else:
                return "empty", ["empty"]
